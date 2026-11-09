# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import codecs
import importlib.util
import io
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import protos_adapter as protos

ROOT = Path(__file__).resolve().parents[3]
HELPERS = (
    ROOT / "runtimes" / "v1" / "azure_functions_runtime_v1"
    / "host_configuration.py",
    ROOT / "runtimes" / "v2" / "azure_functions_runtime"
    / "host_configuration.py",
)
ENCODINGS = (
    ("utf-8", b""),
    ("utf-8", codecs.BOM_UTF8),
    ("utf-16-le", codecs.BOM_UTF16_LE),
    ("utf-16-be", codecs.BOM_UTF16_BE),
    ("utf-32-le", codecs.BOM_UTF32_LE),
    ("utf-32-be", codecs.BOM_UTF32_BE),
)


@pytest.fixture(params=HELPERS, ids=("v1", "v2"))
def helper(request, monkeypatch, tmp_path):
    # Load the independently packaged implementation without importing an SDK
    # or transport. The same contract suite also runs in protobuf-free R2P2 CI.
    name = "_host_configuration_test"
    monkeypatch.setitem(sys.modules, name + ".logging", SimpleNamespace(
        logger=logging.getLogger(name)))
    spec = importlib.util.spec_from_file_location(
        name + ".host_configuration", request.param)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", str(tmp_path))
    monkeypatch.delenv("AzureWebJobsScriptRoot", raising=False)
    return module


def snapshot(helper):
    return helper.get_host_configuration(
        {"HostConfiguration": "1"}, protos)["host_configuration"]


def assert_snapshot(result, status, content=b""):
    assert result.status == status
    assert result.content == content


def test_packaged_implementations_stay_identical():
    assert len({path.read_bytes() for path in HELPERS}) == 1


@pytest.mark.parametrize("capabilities", [
    {}, {"HostConfiguration": ""}, {"HostConfiguration": "true"},
    {"HostConfiguration": "True"}, {"HostConfiguration": "01"},
    {"HostConfiguration": " 1"}, {"HostConfiguration": "1 "},
    {"hostconfiguration": "1"}, {"HOSTCONFIGURATION": "1"},
])
def test_disabled_does_not_obtain_root_initialize_or_read(helper, capabilities):
    with patch.object(helper.os.environ, "get") as root, \
            patch.object(helper, "open", create=True) as read, \
            patch.object(helper, "_capture") as capture, \
            patch.object(helper.logger, "warning") as warning:
        assert helper.get_host_configuration(capabilities, object()) == {}
    root.assert_not_called()
    read.assert_not_called()
    capture.assert_not_called()
    warning.assert_not_called()
    assert helper._snapshot is None


@pytest.mark.parametrize("root", [None, "", " ", "\t\r\n", "\0"])
def test_unset_non_linux_or_invalid_root_is_error(helper, monkeypatch, root):
    monkeypatch.setattr(helper, "sys", SimpleNamespace(platform="win32"))
    if root is None:
        monkeypatch.delenv("FUNCTIONS_APPLICATION_DIRECTORY")
    elif root == "\0":
        with patch.object(helper.os.environ, "get", return_value=root):
            assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
        return
    else:
        monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", root)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


def test_explicit_directory_takes_precedence(helper, tmp_path, monkeypatch):
    explicit = tmp_path / " explicit"
    explicit.mkdir()
    (explicit / "host.json").write_bytes(b'{"root":"explicit"}')
    (tmp_path / "host.json").write_bytes(b'{"root":"script"}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", explicit.name)
    monkeypatch.setenv("AzureWebJobsScriptRoot", str(tmp_path))
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"root":"explicit"}')


@pytest.mark.parametrize("root", [None, "", " \t"])
def test_script_root_fallback(helper, tmp_path, monkeypatch, root):
    if root is None:
        monkeypatch.delenv("FUNCTIONS_APPLICATION_DIRECTORY")
    else:
        monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", root)
    monkeypatch.setenv("AzureWebJobsScriptRoot", str(tmp_path))
    (tmp_path / "host.json").write_bytes(b'{"root":"script"}')
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"root":"script"}')


@pytest.mark.parametrize("root", [None, "", " \t"])
def test_linux_default_directory(helper, monkeypatch, root):
    for setting in ("FUNCTIONS_APPLICATION_DIRECTORY", "AzureWebJobsScriptRoot"):
        if root is None:
            monkeypatch.delenv(setting, raising=False)
        else:
            monkeypatch.setenv(setting, root)
    monkeypatch.setattr(helper, "sys", SimpleNamespace(platform="linux"))
    with patch.object(helper, "open", create=True,
                      return_value=io.BytesIO(b'{"root":"default"}')) as read:
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                        b'{"root":"default"}')
    read.assert_called_once_with(
        helper.os.path.join("/home/site/wwwroot", "host.json"), "rb")


@pytest.mark.parametrize("setting", [
    "FUNCTIONS_APPLICATION_DIRECTORY", "AzureWebJobsScriptRoot",
])
def test_selected_directory_error_does_not_fall_back(
        helper, tmp_path, monkeypatch, setting):
    missing = tmp_path / "absent"
    (tmp_path / "host.json").write_bytes(b'{"root":"fallback"}')
    monkeypatch.setenv("AzureWebJobsScriptRoot", str(tmp_path))
    if setting == "AzureWebJobsScriptRoot":
        monkeypatch.delenv("FUNCTIONS_APPLICATION_DIRECTORY")
    monkeypatch.setenv(setting, str(missing))
    monkeypatch.setattr(helper, "sys", SimpleNamespace(platform="linux"))
    with patch.object(helper, "open", create=True, wraps=open) as read:
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    read.assert_called_once_with(
        helper.os.path.join(str(missing), "host.json"), "rb")


def test_missing_file_differs_from_missing_directory(
        helper, tmp_path, monkeypatch):
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Missing)
    with helper.reset_host_configuration():
        pass
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY",
                       str(tmp_path / "absent"))
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


def test_non_directory_root_and_directory_file(helper, tmp_path, monkeypatch):
    (tmp_path / "not-a-directory").write_bytes(b"")
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY",
                       str(tmp_path / "not-a-directory"))
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    with helper.reset_host_configuration():
        pass
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", str(tmp_path))
    (tmp_path / "host.json").mkdir()
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


def test_relative_root_keeps_native_resolution(helper, tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "host.json").write_bytes(b'{"path":"relative"}')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", "app")
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"path":"relative"}')


@pytest.mark.parametrize("text", ["{}", '{"secret":"\u20ac\U0001f600"}'])
@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_encodings(helper, tmp_path, encoding, bom, text):
    (tmp_path / "host.json").write_bytes(bom + text.encode(encoding))
    with patch.object(helper.os, "stat") as stat:
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                        text.encode("utf-8"))
    stat.assert_not_called()


@pytest.mark.parametrize("text", [
    "", "[]", '"string"', "1E+2", "null", "true", "false",
    "/* leading */ []", "// leading\n[]", '/* leading */ "string"',
    "/* leading */ 1E+2", "/* leading */ null", "/* leading */ true",
    "/* leading */ false",
], ids=("empty", "array", "string", "number", "null", "true", "false",
        "comment-array", "line-comment-array", "comment-string",
        "comment-number", "comment-null", "comment-true", "comment-false"))
@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_empty_and_non_object_roots_are_cached_invalid_json(
        helper, tmp_path, encoding, bom, text, caplog):
    path = tmp_path / "host.json"
    path.write_bytes(bom + text.encode(encoding))
    first = snapshot(helper)
    assert_snapshot(first, protos.HostConfiguration.Error)
    path.write_bytes(b"{}")
    with patch.object(helper.os.environ, "get") as root, \
            patch.object(helper, "open", create=True) as read:
        repeated = snapshot(helper)
    root.assert_not_called()
    read.assert_not_called()
    assert repeated is not first
    assert_snapshot(repeated, protos.HostConfiguration.Error)
    assert caplog.messages == [
        "Host configuration could not be delivered to the host. "
        "Reason: InvalidJson. The failure is retained until the worker "
        "process restarts."]


@pytest.mark.parametrize("encoding,bom", ENCODINGS)
@pytest.mark.parametrize("size", [65536, 65537])
@pytest.mark.parametrize("character", ["a", "\u0800", "\U0001f600"])
def test_final_byte_limit_not_source_length(
        helper, tmp_path, encoding, bom, size, character):
    width = len(character.encode("utf-8"))
    prefix, suffix = '{"value":"', '"}'
    payload_size = size - len(prefix) - len(suffix)
    text = (prefix + character * (payload_size // width)
            + "a" * (payload_size % width) + suffix)
    assert len(text.encode("utf-8")) == size
    source = bom + text.encode(encoding)
    (tmp_path / "host.json").write_bytes(source)
    expected = (protos.HostConfiguration.Available if size == 65536
                else protos.HostConfiguration.TooLarge)
    content = text.encode("utf-8") if size == 65536 else b""
    assert_snapshot(snapshot(helper), expected, content)


@pytest.mark.parametrize("source", [
    b"\xff", b"\xc0\xaf", b"\xed\xa0\x80", b"\xf4\x90\x80\x80",
    b"a" * 4099 + b"\xe2\x82", codecs.BOM_UTF8 + b"\xf0\x9f",
    codecs.BOM_UTF16_LE + b"\x00", codecs.BOM_UTF16_BE + b"\x00",
    codecs.BOM_UTF16_LE + b"\x00\xd8",
    codecs.BOM_UTF16_BE + b"\xd8\x00",
    codecs.BOM_UTF32_LE + b"\x00\x00\x11\x00",
    codecs.BOM_UTF32_BE + b"\x00\x11\x00\x00",
    codecs.BOM_UTF32_LE + b"\x00\xd8\x00\x00",
    codecs.BOM_UTF32_BE + b"\x00\x00\xd8\x00",
    codecs.BOM_UTF32_LE + b"\x00\x00",
    codecs.BOM_UTF32_BE + b"\x00\x00",
])
def test_invalid_or_truncated_encoding_is_error(helper, tmp_path, source):
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


@pytest.mark.parametrize("source,status", [
    (b"{}", protos.HostConfiguration.Available),
    (None, protos.HostConfiguration.Missing),
    (b"\xff", protos.HostConfiguration.Error),
    (b"x" * 65537, protos.HostConfiguration.TooLarge),
], ids=("available", "missing", "error", "too-large"))
def test_caches_all_outcomes_and_returns_fresh_envelopes(
        helper, tmp_path, source, status):
    path = tmp_path / "host.json"
    if source is not None:
        path.write_bytes(source)
    first = snapshot(helper)
    assert first.status == status
    original_content = first.content
    first.content = b"mutated response"
    first.status = protos.HostConfiguration.Unspecified
    path.write_bytes(b'{"value":"replacement"}')
    with patch.object(helper.os.environ, "get") as root, \
            patch.object(helper, "open", create=True) as read:
        second = snapshot(helper)
        assert helper.get_host_configuration({}, object()) == {}
    root.assert_not_called()
    read.assert_not_called()
    assert second is not first
    assert_snapshot(second, status, original_content)
    with helper.reset_host_configuration():
        pass
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"value":"replacement"}')


@pytest.mark.parametrize("source,status", [
    (b"{}", protos.HostConfiguration.Available),
    (b"\xff", protos.HostConfiguration.Error),
    (b"", protos.HostConfiguration.Error),
    (b"[]", protos.HostConfiguration.Error),
])
def test_concurrent_first_requests_capture_once(
        helper, tmp_path, source, status, caplog):
    (tmp_path / "host.json").write_bytes(source)
    barrier = threading.Barrier(8)

    def request(_):
        barrier.wait()
        return snapshot(helper)

    with patch.object(helper, "_capture", wraps=helper._capture) as capture:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(request, range(8)))
    capture.assert_called_once()
    assert all(result.status == status for result in results)
    assert len({id(result) for result in results}) == 8
    assert len(caplog.messages) == (1 if status == protos.HostConfiguration.Error
                                    else 0)


@pytest.mark.parametrize("failure", [
    PermissionError("secret-path"), OSError("secret-content"),
    FileNotFoundError("secret-path"), RuntimeError("secret-value"),
])
def test_root_accessor_errors_are_cached_and_safe(helper, failure, caplog):
    root = Mock(side_effect=failure)
    with patch.object(helper, "os", SimpleNamespace(
            environ=SimpleNamespace(get=root))):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    root.assert_called_once_with("FUNCTIONS_APPLICATION_DIRECTORY")
    assert "secret" not in caplog.text
    assert len(caplog.messages) == 1
    assert "Reason: AppDirectoryUnavailable." in caplog.messages[0]


def test_permission_read_and_parent_access_errors(helper):
    with patch.object(helper, "open", create=True,
                      side_effect=PermissionError("private-path")):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    with helper.reset_host_configuration():
        pass
    with patch.object(helper.os, "stat",
                      side_effect=PermissionError("private-parent")):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    with helper.reset_host_configuration():
        pass
    with patch.object(helper, "open", create=True) as read:
        read.return_value.read.side_effect = (
            FileNotFoundError("disappeared after open"))
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


class BoundedStream(io.BytesIO):
    def __init__(self, content, short_reads=False):
        super().__init__(content)
        self.bytes_read = 0
        self.short_reads = short_reads

    def read(self, size=-1):
        assert 0 < size <= 4096
        content = super().read(min(size, 1) if self.short_reads else size)
        self.bytes_read += len(content)
        return content


def test_specialization_excludes_concurrent_capture(
        helper, tmp_path, monkeypatch):
    (tmp_path / "host.json").write_bytes(b'{"value":"old"}')
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"value":"old"}')
    next_app = tmp_path / "next"
    next_app.mkdir()
    (next_app / "host.json").write_bytes(b'{"value":"new"}')
    started = threading.Event()

    def request():
        started.set()
        return snapshot(helper)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with helper.reset_host_configuration():
            pending = pool.submit(request)
            assert started.wait(timeout=5)
            assert not pending.done()
            monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", str(next_app))
        assert_snapshot(pending.result(timeout=5),
                        protos.HostConfiguration.Available, b'{"value":"new"}')


def test_oversized_stream_stops_with_bounded_acquisition(helper):
    stream = BoundedStream(b"x" * 1000000)
    with patch.object(helper, "open", create=True, return_value=stream):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.TooLarge)
    assert stream.bytes_read <= 65536 + 4096
    assert stream.closed


@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_short_reads_and_split_multibyte_sequences(helper, encoding, bom):
    text = '{"value":"' + "\u20ac\U0001f600" * 100 + '"}'
    stream = BoundedStream(bom + text.encode(encoding), short_reads=True)
    with patch.object(helper, "open", create=True, return_value=stream):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                        text.encode("utf-8"))


@pytest.mark.parametrize("source,expected", [
    (b"{}", b"{}"),
    (b"/* before */ {} // after", b"{}"),
    (b'// header\n{ "version": "2.0", /* inline */ "a": [1, 2,], }',
     b'{"version":"2.0","a":[1,2]}'),
    (b'{"a":1,"a":2,"\\u0061":3}', b'{"a":1,"a":2,"\\u0061":3}'),
    (b'{"s":"x\\u0041\\n\\/\\ud800","n":[-0,1E+2,1e999,-0.50]}',
     b'{"s":"x\\u0041\\n\\/\\ud800","n":[-0,1E+2,1e999,-0.50]}'),
    (b'{"v":[{},[],true,false,null,"// /* text */",]}',
     b'{"v":[{},[],true,false,null,"// /* text */"]}'),
    (b'{"v":/* before */ 1 /* after */}', b'{"v":1}'),
    (b'{"v": true} // end', b'{"v":true}'),
    (b'{"v":false}\r\n', b'{"v":false}'),
    (b'{"v":null}', b'{"v":null}'),
    (b'{"v":"string"}', b'{"v":"string"}'),
    (b'{"v":["\\udfff","\\ud800\\udc00","\\uD800X"]}',
     b'{"v":["\\udfff","\\ud800\\udc00","\\uD800X"]}'),
    (b'{"\\udc00\\ud800":"\\udc00\\ud800"}',
     b'{"\\udc00\\ud800":"\\udc00\\ud800"}'),
    (b'{"v":123456789012345678901234567890.123456789012345678901}',
     b'{"v":123456789012345678901234567890.123456789012345678901}'),
], ids=("empty-object", "commented-empty-object", "jsonc", "duplicate-keys",
        "raw-tokens", "containers", "number", "true", "false", "null",
        "string", "surrogates", "reversed-surrogates", "precision"))
def test_compact_normalization_preserves_tokens(
        helper, tmp_path, source, expected):
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    expected)


@pytest.mark.parametrize("source", [
    b" ", b"\r\n\t", b"// only", b"/* only */", b"not json", b"{",
    b"{} {}", b'{"a":1 2}', b'{"a":1/* gap */2}', b'{"a":tr/* gap */ue}',
    b'{"a":true false}', b'{"a":[,]}', b"{,}", b'{"a":[1,,]}',
    b'{"a":,}', b'{"a":1,,}', b'{"a" 1}', b'{"a":1 "b":2}', b'{"a":[1 2]}',
    b'{"a":[}', b'{"a":"unterminated', b'{"a":"\\q"}', b'{"a":"\\u123z"}',
    b'{"a":"unescaped\n"}', b'{"a":01}', b'{"a":1.}', b'{"a":1e}',
    b'{"a":+1}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":-Infinity}',
    b"/* unterminated", b"{} trailing", b"{} /* unterminated",
    b"\xc2\xa0{}", b"\x0b{}", b"\x0c{}", b"\xef\xbb\xbf\xef\xbb\xbf{}",
])
def test_invalid_json_is_cached_content_free_error(
        helper, tmp_path, source, caplog):
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert caplog.messages == [
        "Host configuration could not be delivered to the host. "
        "Reason: InvalidJson. The failure is retained until the worker "
        "process restarts."]


@pytest.mark.parametrize("depth,status", [
    (64, protos.HostConfiguration.Available),
    (65, protos.HostConfiguration.Error),
])
@pytest.mark.parametrize("opening,closing", [(b"[", b"]"), (b'{"x":', b"}")])
def test_json_depth_limit(helper, tmp_path, depth, status, opening, closing):
    source = b'{"x":' + opening * (depth - 1) + b"0" + closing * (depth - 1) + b"}"
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), status,
                    source if status == protos.HostConfiguration.Available
                    else b"")


def test_large_integer_does_not_use_python_digit_limit(helper, tmp_path):
    source = b'{"value":' + b"9" * 6000 + b"}"
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available, source)


@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_valid_replacement_character_is_not_invalid_encoding(
        helper, tmp_path, encoding, bom):
    text = '{"value":"\ufffd"}'
    (tmp_path / "host.json").write_bytes(bom + text.encode(encoding))
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    text.encode("utf-8"))


@pytest.mark.parametrize("separator", ["\u2028", "\u2029"])
@pytest.mark.parametrize("context,status", [
    ('// {0}\n{{}}', protos.HostConfiguration.Error),
    ('{{}}// {0}', protos.HostConfiguration.Error),
    ('/* {0} */{{}}', protos.HostConfiguration.Available),
    ('{{"key":"{0}"}}', protos.HostConfiguration.Available),
    ('{{{0}}}', protos.HostConfiguration.Error),
])
def test_unicode_separators_in_comments_strings_and_whitespace(
        helper, tmp_path, separator, context, status):
    source = context.format(separator).encode("utf-8")
    (tmp_path / "host.json").write_bytes(source)
    expected = (source if source.startswith(b'{"key"') else b"{}")
    assert_snapshot(snapshot(helper), status,
                    expected if status == protos.HostConfiguration.Available
                    else b"")


@pytest.mark.parametrize("terminator", [b"\r", b"\n", b"\r\n"])
def test_line_comment_terminators(helper, tmp_path, terminator):
    source = b"// comment" + terminator + b'{"a":1, // comment' + terminator + b"}"
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b'{"a":1}')


@pytest.mark.parametrize("source", [None, b"{}", codecs.BOM_UTF16_LE + b"{\0}\0"])
def test_available_and_missing_do_not_warn(
        helper, tmp_path, source, caplog):
    if source is not None:
        (tmp_path / "host.json").write_bytes(source)
    expected = (protos.HostConfiguration.Missing if source is None
                else protos.HostConfiguration.Available)
    assert snapshot(helper).status == expected
    assert snapshot(helper).status == expected
    assert not caplog.messages


@pytest.mark.parametrize("source,status,reason", [
    (b"", protos.HostConfiguration.Error, "InvalidJson"),
    (b"[]", protos.HostConfiguration.Error, "InvalidJson"),
    (b"{secret", protos.HostConfiguration.Error, "InvalidJson"),
    (b"\xffsecret", protos.HostConfiguration.Error, "InvalidEncoding"),
    (b"x" * 65537, protos.HostConfiguration.TooLarge, "Oversized"),
], ids=("empty", "array", "json", "encoding", "oversized"))
def test_failure_reason_is_logged_once_per_generation(
        helper, tmp_path, source, status, reason, caplog):
    (tmp_path / "host.json").write_bytes(source)
    assert_snapshot(snapshot(helper), status)
    assert_snapshot(snapshot(helper), status)
    assert helper.get_host_configuration({}, object()) == {}
    assert len(caplog.messages) == 1
    assert f"Reason: {reason}." in caplog.messages[0]
    assert "secret" not in caplog.text
    assert str(tmp_path) not in caplog.text
    with helper.reset_host_configuration():
        pass
    assert_snapshot(snapshot(helper), status)
    assert len(caplog.messages) == 2


@pytest.mark.parametrize("error,reason", [
    (PermissionError("secret-path"), "AccessDenied"),
    (NotADirectoryError("secret-path"), "AppDirectoryNotFound"),
    (OSError("secret-path"), "OpenFailed"),
])
def test_open_failure_reasons(helper, error, reason, caplog):
    with patch.object(helper, "open", create=True, side_effect=error):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert f"Reason: {reason}." in caplog.messages[0]
    assert "secret" not in caplog.text


@pytest.mark.parametrize("root,reason", [
    (None, "AppDirectoryNotSet"), (" ", "AppDirectoryNotSet"),
    (object(), "AppDirectoryInvalid"),
])
def test_root_failure_reasons(helper, root, reason, caplog):
    with patch.object(helper, "sys", SimpleNamespace(platform="win32")), \
            patch.object(helper.os.environ, "get", return_value=root):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert f"Reason: {reason}." in caplog.messages[0]


def test_root_join_failure_is_safe(helper, caplog):
    with patch.object(helper.os.path, "join",
                      side_effect=ValueError("private-path")):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert "Reason: AppDirectoryInvalid." in caplog.messages[0]
    assert "private" not in caplog.text


@pytest.mark.parametrize("stage", ["read", "close"])
@pytest.mark.parametrize("error", [FileNotFoundError, PermissionError, OSError])
def test_failures_after_open_are_read_failed(helper, stage, error, caplog):
    with patch.object(helper, "open", create=True) as opened:
        stream = opened.return_value
        if stage == "read":
            stream.read.side_effect = error("private-path")
        else:
            stream.read.side_effect = [b"{}", b"", b""]
            stream.__exit__.side_effect = error("private-path")
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
    assert len(caplog.messages) == 1
    assert "Reason: ReadFailed." in caplog.messages[0]
    assert "private" not in caplog.text


def test_converted_limit_applies_before_comment_removal(helper, tmp_path):
    (tmp_path / "host.json").write_bytes(b"/*" + b"x" * 65531 + b"*/{}")
    assert_snapshot(snapshot(helper), protos.HostConfiguration.TooLarge)


def test_normalized_output_has_an_independent_limit(helper, tmp_path):
    (tmp_path / "host.json").write_bytes(b"{}")
    with patch.object(helper, "_normalize", return_value=b"x" * 65537):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.TooLarge)
