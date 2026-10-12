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


def test_prioritization_preserves_namespace_and_cached_customer_child(
        monkeypatch, tmp_path, restore_sys_path):
    workers_dir = tmp_path / "workers"
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    package_name = "r2p2_namespace_customer_cache"
    child_name = f"{package_name}.child"
    worker_namespace = workers_dir / package_name
    customer_namespace = site / package_name
    worker_namespace.mkdir(parents=True)
    customer_namespace.mkdir(parents=True)
    customer_namespace.joinpath("child.py").write_text(
        "VERSION = 'customer'\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))
    sys.path[:0] = [str(workers_dir), str(site)]

    try:
        child = importlib.import_module(child_name)
        namespace = importlib.import_module(package_name)
        assert namespace.__file__ is None
        assert set(namespace.__path__) == {
            str(worker_namespace), str(customer_namespace)}
        assert namespace.child is child

        bridge._prioritize_customer_dependencies(str(app_dir))

        assert sys.modules[package_name] is namespace
        assert sys.modules[child_name] is child
        assert namespace.child.VERSION == "customer"
        assert namespace.child is child
        assert importlib.import_module(package_name) is namespace
        assert importlib.import_module(child_name) is child
        assert __import__(package_name, fromlist=["child"]).child is child
    finally:
        for module_name in (child_name, package_name):
            sys.modules.pop(module_name, None)


@pytest.mark.parametrize(
    "reassign_child", [False, True],
    ids=["evicted-module-attribute", "reassigned-sentinel"])
def test_prioritization_detaches_only_evicted_namespace_child(
        monkeypatch, tmp_path, restore_sys_path, reassign_child):
    workers_dir = tmp_path / "workers"
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    package_name = "r2p2_namespace_from_import"
    child_name = f"{package_name}.child"
    for root, version in ((workers_dir, "worker"), (site, "customer")):
        namespace_dir = root / package_name
        namespace_dir.mkdir(parents=True)
        namespace_dir.joinpath("child.py").write_text(
            f"VERSION = {version!r}\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))
    sys.path[:0] = [str(workers_dir), str(site)]
    sentinel = object()

    try:
        worker_child = importlib.import_module(child_name)
        namespace = importlib.import_module(package_name)
        assert worker_child.VERSION == "worker"
        assert namespace.child is worker_child
        if reassign_child:
            namespace.child = sentinel

        bridge._prioritize_customer_dependencies(str(app_dir))

        assert sys.modules[package_name] is namespace
        assert child_name not in sys.modules
        imported = __import__(package_name, fromlist=["child"])
        assert imported is namespace
        if reassign_child:
            assert imported.child is sentinel
            assert child_name not in sys.modules
        else:
            assert imported.child.VERSION == "customer"
            assert imported.child is not worker_child
            assert sys.modules[child_name] is imported.child
    finally:
        for module_name in (child_name, package_name):
            sys.modules.pop(module_name, None)


def test_prioritization_evicts_regular_worker_package_and_customer_child(
        monkeypatch, tmp_path, restore_sys_path):
    workers_dir = tmp_path / "workers"
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    package_name = "r2p2_regular_extended_path"
    child_name = f"{package_name}.child"
    worker_package = workers_dir / package_name
    customer_package = site / package_name
    worker_package.mkdir(parents=True)
    customer_package.mkdir(parents=True)
    worker_package.joinpath("__init__.py").write_text(
        "VERSION = 'worker'\n"
        f"__path__.append({str(customer_package)!r})\n",
        encoding="utf-8")
    customer_package.joinpath("__init__.py").write_text(
        "VERSION = 'customer'\n", encoding="utf-8")
    customer_package.joinpath("child.py").write_text(
        "VERSION = 'customer'\n", encoding="utf-8")
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))
    sys.path[:0] = [str(workers_dir), str(site)]

    try:
        old_child = importlib.import_module(child_name)
        old_package = importlib.import_module(package_name)
        assert old_package.VERSION == "worker"
        assert old_package.__path__ == [
            str(worker_package), str(customer_package)]
        assert old_child.__file__ == str(customer_package / "child.py")
        assert old_package.child is old_child

        bridge._prioritize_customer_dependencies(str(app_dir))

        assert package_name not in sys.modules
        assert child_name not in sys.modules
        new_package = importlib.import_module(package_name)
        new_child = importlib.import_module(child_name)
        assert new_package is not old_package
        assert new_child is not old_child
        assert new_package.VERSION == "customer"
        assert new_child.VERSION == "customer"
        assert new_package.child is new_child
    finally:
        for module_name in (child_name, package_name):
            sys.modules.pop(module_name, None)


def test_prioritization_refreshes_namespace_with_unchanged_sys_path(
        monkeypatch, tmp_path, restore_sys_path):
    workers_dir = tmp_path / "workers"
    app_dir = tmp_path / "app"
    site = app_dir / ".python_packages" / "lib" / "site-packages"
    package_name = "r2p2_namespace_new_portion"
    child_name = f"{package_name}.child"
    worker_namespace = workers_dir / package_name
    customer_namespace = site / package_name
    worker_namespace.mkdir(parents=True)
    site.mkdir(parents=True)
    monkeypatch.setattr(bridge, "_workers_dir", str(workers_dir))
    sys.path[:] = [str(site), str(workers_dir), *sys.path, str(app_dir)]
    original_path = tuple(sys.path)

    try:
        namespace = importlib.import_module(package_name)
        assert namespace.__file__ is None
        assert list(namespace.__path__) == [str(worker_namespace)]
        assert not customer_namespace.exists()

        customer_namespace.mkdir()
        customer_namespace.joinpath("child.py").write_text(
            "VERSION = 'customer'\n", encoding="utf-8")

        bridge._prioritize_customer_dependencies(str(app_dir))

        assert tuple(sys.path) == original_path
        assert sys.modules[package_name] is namespace
        imported = __import__(package_name, fromlist=["child"])
        assert imported is namespace
        assert imported.child.VERSION == "customer"
        assert imported.child.__file__ == str(customer_namespace / "child.py")
        assert str(customer_namespace) in namespace.__path__
        assert sys.modules[child_name] is imported.child
    finally:
        for module_name in (child_name, package_name):
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
