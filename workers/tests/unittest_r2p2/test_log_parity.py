# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Log-parity tests. R2P2 must emit the SAME control-request System log lines as
# the classic proxy worker (3.13) so existing Kusto queries keep parsing without
# a Python-3.15-specific variant. These lock the exact text of
# ``_log_control_received`` -- including the WorkerMetadataRequest /
# WorkerLoadRequest naming quirk and the request-ID/worker-ID fields.

import logging

import pytest

import bridge


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)

    @property
    def last_message(self):
        return self.records[-1].getMessage()


@pytest.fixture
def syslog_capture():
    logger = logging.getLogger("azure_functions_runtime")
    handler = _Capture()
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)


@pytest.fixture(autouse=True)
def _ids(monkeypatch):
    # request_id / worker_id are startup-scoped globals (as in the proxy worker).
    monkeypatch.setattr(bridge, "_request_id", "req-1")
    monkeypatch.setattr(bridge, "_worker_id", "wid-1")
    # Keep _worker_version() deterministic (-> "unknown") without a runtime.
    monkeypatch.setattr(bridge, "_rt", None)


def test_worker_init_line(syslog_capture):
    bridge._log_control_received("worker_init_request", {})
    msg = syslog_capture.last_message
    assert msg.startswith("Received WorkerInitRequest, python version ")
    assert "worker version unknown" in msg
    assert "request ID req-1" in msg
    assert "https://aka.ms/python-enable-debug-logging" in msg


def test_functions_metadata_line_uses_worker_metadata_name(syslog_capture):
    bridge._log_control_received("functions_metadata_request", {})
    assert syslog_capture.last_message == (
        "Received WorkerMetadataRequest, request ID req-1, worker id: wid-1"
    )


def test_function_load_line_uses_worker_load_name(syslog_capture):
    bridge._log_control_received(
        "function_load_request",
        {"function_id": "fid-1", "metadata": {"name": "hello"}},
    )
    assert syslog_capture.last_message == (
        "Received WorkerLoadRequest, request ID req-1, function_id: fid-1, "
        "function_name: hello, worker_id: wid-1"
    )


def test_function_load_line_without_metadata(syslog_capture):
    bridge._log_control_received(
        "function_load_request", {"function_id": "fid-1"}
    )
    assert syslog_capture.last_message == (
        "Received WorkerLoadRequest, request ID req-1, function_id: fid-1, "
        "function_name: , worker_id: wid-1"
    )


def test_env_reload_line(syslog_capture):
    bridge._log_control_received("function_environment_reload_request", {})
    assert syslog_capture.last_message == (
        "Received FunctionEnvironmentReloadRequest, request ID: req-1, "
        "To enable debug level logging, please refer to "
        "https://aka.ms/python-enable-debug-logging"
    )


def test_unknown_request_falls_back_to_capitalized_name(syslog_capture):
    bridge._log_control_received("worker_status_request", {})
    assert syslog_capture.last_message == "Received WorkerStatusRequest."
