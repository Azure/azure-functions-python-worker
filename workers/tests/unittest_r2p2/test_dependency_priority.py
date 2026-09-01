# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Tests for the customer-dependency prioritization -- the R2P2 equivalent of the
# proxy worker's DependencyManager.prioritize_customer_dependencies. Verifies the
# final sys.path search order (customer deps > worker deps > app dir), the
# reload-time re-prioritization contract, and the ``Finished
# prioritize_customer_dependencies`` System log (matched by test_flex_consumption
# and Kusto).

import logging
import sys

import pytest

import bridge


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


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


@pytest.fixture
def restore_sys_path():
    saved = list(sys.path)
    try:
        yield
    finally:
        sys.path[:] = saved


# --- _reprioritize_path ---------------------------------------------------
def test_reprioritize_front_dedupes(restore_sys_path):
    sys.path[:] = ["/a", "/b", "/target", "/c", "/target"]
    bridge._reprioritize_path("/target", front=True)
    assert sys.path[0] == "/target"
    assert sys.path.count("/target") == 1


def test_reprioritize_back_dedupes(restore_sys_path):
    sys.path[:] = ["/target", "/a", "/b"]
    bridge._reprioritize_path("/target", front=False)
    assert sys.path[-1] == "/target"
    assert sys.path.count("/target") == 1


def test_reprioritize_empty_is_noop(restore_sys_path):
    before = list(sys.path)
    bridge._reprioritize_path("", front=True)
    assert sys.path == before


# --- _customer_deps_path --------------------------------------------------
def test_customer_deps_path_resolves_azure_layout(tmp_path):
    site = tmp_path / ".python_packages" / "lib" / "site-packages"
    site.mkdir(parents=True)
    assert bridge._customer_deps_path(str(tmp_path)) == str(site)


def test_customer_deps_path_missing_returns_empty(tmp_path):
    assert bridge._customer_deps_path(str(tmp_path)) == ""


# --- _prioritize_customer_dependencies ------------------------------------
def test_prioritization_orders_sys_path(monkeypatch, tmp_path,
                                        restore_sys_path):
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    site.mkdir(parents=True)
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))

    cx = bridge._prioritize_customer_dependencies(str(app_dir))

    assert cx == str(site)
    # Highest priority first: customer deps, then worker deps, then app dir last.
    assert sys.path[0] == str(site)
    assert sys.path[1] == str(workers_dir)
    assert sys.path[-1] == str(app_dir)


def test_prioritization_without_customer_deps(monkeypatch, tmp_path,
                                              restore_sys_path):
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))

    cx = bridge._prioritize_customer_dependencies(str(app_dir))

    assert cx == ""
    assert sys.path[0] == str(workers_dir)
    assert sys.path[-1] == str(app_dir)


def test_prioritization_emits_finished_log(monkeypatch, tmp_path,
                                           restore_sys_path, syslog_capture):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))

    bridge._prioritize_customer_dependencies(str(tmp_path))

    messages = [r.getMessage() for r in syslog_capture.records]
    assert any(
        m.startswith("Finished prioritize_customer_dependencies: "
                     "worker_dependencies_path: ")
        for m in messages
    )
