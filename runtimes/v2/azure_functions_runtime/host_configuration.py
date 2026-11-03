# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""One immutable host.json snapshot per application generation."""

import codecs
import os
import stat
import threading
from contextlib import contextmanager

from .logging import logger

_MAX_BYTES = 65536
_READ_SIZE = 4096
_lock = threading.Lock()
_snapshot = None


def get_host_configuration(capabilities, protos):
    """Return optional response fields, without touching the root if disabled."""
    if ("HostConfiguration" not in capabilities
            or capabilities["HostConfiguration"] != "1"):
        return {}

    global _snapshot
    with _lock:
        if _snapshot is None:
            _snapshot = _capture(protos.HostConfiguration)
        status, content = _snapshot

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
    try:
        root = os.environ.get("FUNCTIONS_APPLICATION_DIRECTORY")
        if not root or not root.strip():
            raise ValueError("Application directory is not configured")
        try:
            stream = open(os.path.join(root, "host.json"), "rb")
        except FileNotFoundError:
            # ENOENT can also mean a missing parent. Do not preflight good reads.
            if stat.S_ISDIR(os.stat(root).st_mode):
                return statuses.Missing, b""
            raise

        with stream:
            content = _read_content(stream)
        if content is None:
            logger.warning("Host configuration delivery exceeded the byte limit.")
            return statuses.TooLarge, b""
        return statuses.Available, content
    except Exception:
        # Root access, IO and strict conversion failures are delivery outcomes,
        # not worker initialization failures. Never log paths or file contents.
        logger.warning("Host configuration delivery failed.")
        return statuses.Error, b""


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
