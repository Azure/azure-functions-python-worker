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
    ROOT / "workers" / "azure_functions_worker" / "host_configuration.py",
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


@pytest.fixture(params=HELPERS, ids=("classic", "v1", "v2"))
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
            patch.object(helper, "_capture") as capture:
        assert helper.get_host_configuration(capabilities, object()) == {}
    root.assert_not_called()
    read.assert_not_called()
    capture.assert_not_called()
    assert helper._snapshot is None


@pytest.mark.parametrize("root", [None, "", " ", "\t\r\n", "\0"])
def test_invalid_root_is_content_free_error(helper, monkeypatch, root):
    if root is None:
        monkeypatch.delenv("FUNCTIONS_APPLICATION_DIRECTORY")
    elif root == "\0":
        with patch.object(helper.os.environ, "get", return_value=root):
            assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)
        return
    else:
        monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", root)
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Error)


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
    (tmp_path / "app" / "host.json").write_bytes(b"relative")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FUNCTIONS_APPLICATION_DIRECTORY", "app")
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                    b"relative")


@pytest.mark.parametrize("text", ["", "{bad json", '{"secret":"\u20ac\U0001f600"}'])
@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_encodings_and_unparsed_json(helper, tmp_path, encoding, bom, text):
    (tmp_path / "host.json").write_bytes(bom + text.encode(encoding))
    with patch.object(helper.os, "stat") as stat:
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                        text.encode("utf-8"))
    stat.assert_not_called()


@pytest.mark.parametrize("encoding,bom", ENCODINGS)
@pytest.mark.parametrize("size", [65536, 65537])
@pytest.mark.parametrize("character", ["a", "\u0800", "\U0001f600"])
def test_final_byte_limit_not_source_length(
        helper, tmp_path, encoding, bom, size, character):
    width = len(character.encode("utf-8"))
    text = character * (size // width) + "a" * (size % width)
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
    path.write_bytes(b"replacement")
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
                    b"replacement")


@pytest.mark.parametrize("source,status", [
    (b"{}", protos.HostConfiguration.Available),
    (b"\xff", protos.HostConfiguration.Error),
])
def test_concurrent_first_requests_capture_once(
        helper, tmp_path, source, status):
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
    (tmp_path / "host.json").write_bytes(b"old")
    assert_snapshot(snapshot(helper), protos.HostConfiguration.Available, b"old")
    next_app = tmp_path / "next"
    next_app.mkdir()
    (next_app / "host.json").write_bytes(b"new")
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
                        protos.HostConfiguration.Available, b"new")


def test_oversized_stream_stops_with_bounded_acquisition(helper):
    stream = BoundedStream(b"x" * 1000000)
    with patch.object(helper, "open", create=True, return_value=stream):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.TooLarge)
    assert stream.bytes_read <= 65536 + 4096
    assert stream.closed


@pytest.mark.parametrize("encoding,bom", ENCODINGS)
def test_short_reads_and_split_multibyte_sequences(helper, encoding, bom):
    text = "\u20ac\U0001f600" * 100
    stream = BoundedStream(bom + text.encode(encoding), short_reads=True)
    with patch.object(helper, "open", create=True, return_value=stream):
        assert_snapshot(snapshot(helper), protos.HostConfiguration.Available,
                        text.encode("utf-8"))
