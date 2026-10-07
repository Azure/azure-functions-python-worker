# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Tests for the customer-dependency prioritization -- the R2P2 equivalent of the
# proxy worker's DependencyManager.prioritize_customer_dependencies. Verifies the
# final sys.path search order (customer deps > worker deps > app dir), the
# reload-time re-prioritization contract, and the ``Finished
# prioritize_customer_dependencies`` System log (matched by test_flex_consumption
# and Kusto).

import importlib
import logging
import sys
from types import ModuleType

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


def test_customer_deps_path_uses_existing_sys_path_entry(
        tmp_path, restore_sys_path):
    site = tmp_path / ".python_packages" / "lib" / "site-packages"
    site.mkdir(parents=True)
    sys.path.insert(0, str(site))

    assert bridge._customer_deps_path("") == str(site)


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


def test_prioritization_reloads_worker_modules_from_customer_deps(
        monkeypatch, tmp_path, restore_sys_path):
    workers_dir = tmp_path / "workers"
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    for root, version in ((workers_dir, "worker"), (site, "customer")):
        package = root / "r2p2_regular_dep"
        package.mkdir(parents=True)
        package.joinpath("__init__.py").write_text(
            f"VERSION = {version!r}\n", encoding="utf-8")
        namespace = root / "r2p2_namespace_dep"
        namespace.mkdir()
        namespace.joinpath("child.py").write_text(
            f"VERSION = {version!r}\n", encoding="utf-8")

    module_names = (
        "r2p2_regular_dep",
        "r2p2_namespace_dep",
        "r2p2_namespace_dep.child",
    )
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))
    sys.path.insert(0, str(workers_dir))
    try:
        regular = importlib.import_module("r2p2_regular_dep")
        namespace_child = importlib.import_module(
            "r2p2_namespace_dep.child")
        assert regular.VERSION == "worker"
        assert namespace_child.VERSION == "worker"

        bridge._prioritize_customer_dependencies(str(app_dir))

        regular = importlib.import_module("r2p2_regular_dep")
        namespace_child = importlib.import_module(
            "r2p2_namespace_dep.child")
        assert regular.VERSION == "customer"
        assert namespace_child.VERSION == "customer"
    finally:
        for module_name in module_names:
            sys.modules.pop(module_name, None)


def test_clear_modules_from_path_preserves_worker_internals(
        monkeypatch, tmp_path):
    workers_dir = tmp_path / "workers"
    package_dir = workers_dir / "package"
    package_dir.mkdir(parents=True)
    stale_module = ModuleType("r2p2_stale_dep")
    stale_module.__file__ = str(package_dir / "stale.py")
    monkeypatch.setitem(sys.modules, stale_module.__name__, stale_module)

    protected_names = (
        "bridge.internal_probe",
        "protos_adapter.internal_probe",
        "azure_functions_runtime.internal_probe",
        "azure_functions_runtime_v1.internal_probe",
    )
    for module_name in protected_names:
        module = ModuleType(module_name)
        module.__file__ = str(package_dir / f"{module_name}.py")
        monkeypatch.setitem(sys.modules, module_name, module)

    monkeypatch.setitem(
        sys.path_importer_cache, str(package_dir), object())

    bridge._clear_modules_from_path(str(workers_dir))

    assert stale_module.__name__ not in sys.modules
    assert all(name in sys.modules for name in protected_names)
    assert str(package_dir) not in sys.path_importer_cache


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


def test_empty_prioritization_tolerates_logging_error(monkeypatch):
    class _BrokenLogger:
        def info(self, *args):
            raise RuntimeError("logger unavailable")

    monkeypatch.setattr(bridge, "_workers_dir", "")
    monkeypatch.setattr(bridge, "_syslog", _BrokenLogger())

    assert bridge._prioritize_customer_dependencies("") == ""
