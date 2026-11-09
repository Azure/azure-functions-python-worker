# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""One immutable host.json snapshot per application generation."""

import codecs
import json
import os
import re
import stat
import sys
import threading
from contextlib import contextmanager

from .logging import logger

_MAX_BYTES = 65536
_READ_SIZE = 4096
_MAX_DEPTH = 64
_JSON_TOKEN = re.compile(
    rb'(?P<trivia>[ \t\r\n]+|//[^\r\n]*|/\*.*?\*/)'
    rb'|"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"'
    rb'|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'
    rb'|true|false|null|[{}\[\],:]', re.DOTALL)
_lock = threading.Lock()
_snapshot = None


class _InvalidJson(ValueError):
    pass


def get_host_configuration(capabilities, protos):
    """Return optional response fields, without touching the root if disabled."""
    if ("HostConfiguration" not in capabilities
            or capabilities["HostConfiguration"] != "1"):
        return {}

    global _snapshot
    with _lock:
        if _snapshot is None:
            _snapshot = _capture(protos.HostConfiguration)
            if _snapshot[2] is not None:
                logger.warning(
                    "Host configuration could not be delivered to the host. "
                    "Reason: %s. The failure is retained until the worker "
                    "process restarts.", _snapshot[2])
        status, content, _ = _snapshot

    return {"host_configuration": protos.HostConfiguration(
        status=status, content=content)}


@contextmanager
def reset_host_configuration():
    """Keep capture blocked while specialization replaces the environment."""
    global _snapshot
    with _lock:
        _snapshot = None
        yield


def _capture(statuses):
    for setting in ("FUNCTIONS_APPLICATION_DIRECTORY", "AzureWebJobsScriptRoot"):
        try:
            root = os.environ.get(setting)
        except Exception:
            return statuses.Error, b"", "AppDirectoryUnavailable"
        try:
            if root and root.strip():
                break
        except Exception:
            return statuses.Error, b"", "AppDirectoryInvalid"
    else:
        root = "/home/site/wwwroot" if sys.platform == "linux" else None

    try:
        if not root or not root.strip():
            return statuses.Error, b"", "AppDirectoryNotSet"
        path = os.path.join(root, "host.json")
    except Exception:
        return statuses.Error, b"", "AppDirectoryInvalid"

    try:
        try:
            stream = open(path, "rb")
        except FileNotFoundError:
            # ENOENT can also mean a missing parent. Do not preflight good reads.
            if stat.S_ISDIR(os.stat(root).st_mode):
                return statuses.Missing, b"", None
            raise NotADirectoryError
    except (FileNotFoundError, NotADirectoryError):
        return statuses.Error, b"", "AppDirectoryNotFound"
    except PermissionError:
        return statuses.Error, b"", "AccessDenied"
    except Exception:
        return statuses.Error, b"", "OpenFailed"

    try:
        with stream:
            content = _read_content(stream)
            if content is not None:
                content = _normalize(content)
        if content is None or len(content) > _MAX_BYTES:
            return statuses.TooLarge, b"", "Oversized"
        return statuses.Available, content, None
    except UnicodeError:
        return statuses.Error, b"", "InvalidEncoding"
    except (json.JSONDecodeError, _InvalidJson):
        return statuses.Error, b"", "InvalidJson"
    except Exception:
        return statuses.Error, b"", "ReadFailed"


def _read_content(stream):
    prefix = b""
    while len(prefix) < 4:
        part = stream.read(4 - len(prefix))
        if not part:
            break
        prefix += part
    encoding = "utf-8"
    for bom, candidate in (
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ):
        if prefix.startswith(bom):
            encoding = candidate
            prefix = prefix[len(bom):]
            break

    decoder = codecs.getincrementaldecoder(encoding)(errors="strict")
    content = bytearray()
    chunk = prefix
    final = False
    while True:
        encoded = decoder.decode(chunk, final=final).encode("utf-8", "strict")
        if len(content) + len(encoded) > _MAX_BYTES:
            return None
        content.extend(encoded)
        if final:
            return bytes(content)
        chunk = stream.read(_READ_SIZE)
        final = not chunk


def _normalize(content):
    """Validate a JSONC object without reserializing its tokens."""
    tokens = []
    validation = bytearray()
    offset = depth = last_token_offset = 0
    while offset < len(content):
        match = _JSON_TOKEN.match(content, offset)
        if match is None:
            raise _InvalidJson
        token = match.group()
        offset = match.end()
        if match.lastgroup == "trivia":
            if token.startswith(b"//") and (
                    b"\xe2\x80\xa8" in token or b"\xe2\x80\xa9" in token):
                raise _InvalidJson
            # Keep token separation: `1 /* comment */ 2` must not become `12`.
            validation.extend(b" ")
            continue
        if token in (b"{", b"["):
            depth += 1
            if depth > _MAX_DEPTH:
                raise _InvalidJson
        elif token in (b"}", b"]"):
            depth -= 1
            if tokens and tokens[-1] == b",":
                # Only a comma following a value may be trailing, not `[,]`.
                if len(tokens) < 2 or tokens[-2] in (b"{", b"[", b":", b","):
                    raise _InvalidJson
                tokens.pop()
                validation[last_token_offset] = ord(" ")
        last_token_offset = len(validation)
        validation.extend(token)
        tokens.append(token)

    if not tokens or tokens[0] != b"{":
        raise _InvalidJson

    # Validate exactly one object without float rounding or Python's integer
    # digit limit. Output uses the original tokens, not the parsed object.
    json.loads(validation, parse_int=str, parse_float=str)
    return b"".join(tokens)
