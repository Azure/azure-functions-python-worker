# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import contextvars
import sys
from importlib.metadata import entry_points
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

import bridge


@pytest.fixture(autouse=True)
def isolated_bridge(monkeypatch):
    for name in ("_rt", "_rt_tls", "_native", "_Datum"):
        monkeypatch.setattr(bridge, name, None)
    monkeypatch.setattr(bridge, "_rt_name", "azure_functions_runtime")
    monkeypatch.setattr(bridge, "_function_app_directory", "")
    monkeypatch.setattr(bridge, "_control_path_cache", {})
    monkeypatch.setattr(bridge, "_workers_dir", "")
    monkeypatch.setattr(bridge, "_host", "")
    monkeypatch.setattr(bridge, "_log_sink", None)
    monkeypatch.setattr(bridge, "_request_id", "")
    monkeypatch.setattr(bridge, "_worker_id", "")
    monkeypatch.setattr(bridge, "_start_loop", lambda: None)
    monkeypatch.setattr(bridge, "_install_rpc_logging", lambda: None)
    monkeypatch.setattr(bridge, "_log", Mock())
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delenv("PYTHON_ENABLE_AGENT_RUNTIME", raising=False)
    for name in ("azure_functions_runtime", "azure_functions_runtime_v1"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))


@pytest.fixture
def agent_runtime(monkeypatch):
    runtime = ModuleType("test_agent_runtime")
    runtime.invocation_id_cv = contextvars.ContextVar("agent", default=None)
    monkeypatch.setitem(sys.modules, runtime.__name__, runtime)
    base = ModuleType("azurefunctions.extensions.base")
    base.RuntimeFeatureChecker = SimpleNamespace(runtime_loaded=lambda: True)
    base.RuntimeTrackerMeta = SimpleNamespace(
        get_package_name=lambda: runtime.__name__)
    monkeypatch.setitem(sys.modules, base.__name__, base)
    ep = SimpleNamespace(name="fastapi", load=Mock())
    discover = Mock(return_value=[ep])
    monkeypatch.setattr(bridge, "entry_points", discover, raising=False)
    return SimpleNamespace(
        runtime=runtime, base=base, entry_point=ep, discover=discover)


@pytest.mark.parametrize("enabled", ["1", "true", " TRUE ", "t", "yes", "y"])
def test_selects_registered_agent_runtime(monkeypatch, agent_runtime, enabled):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", enabled)

    bridge._select_runtime("")

    assert bridge._rt is agent_runtime.runtime
    assert bridge._rt_name == agent_runtime.runtime.__name__
    agent_runtime.discover.assert_called_once_with(
        group="azurefunctions.runtimes")
    agent_runtime.entry_point.load.assert_called_once_with()


@pytest.mark.parametrize("enabled", [None, "0", "false", "no"])
@pytest.mark.parametrize("has_script", [False, True])
def test_disabled_agent_runtime_preserves_standard_selection(
        monkeypatch, tmp_path, agent_runtime, enabled, has_script):
    if enabled is not None:
        monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", enabled)
    if has_script:
        (tmp_path / "function_app.py").touch()
    name = ("azure_functions_runtime" if has_script
            else "azure_functions_runtime_v1")
    runtime = ModuleType(name)
    monkeypatch.setitem(sys.modules, name, runtime)

    bridge._select_runtime(str(tmp_path))

    assert bridge._rt is runtime
    agent_runtime.discover.assert_not_called()


@pytest.mark.parametrize("has_base", [False, True])
def test_no_entry_points_falls_back_to_standard_runtime(
        monkeypatch, tmp_path, agent_runtime, has_base):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")
    if not has_base:
        monkeypatch.setitem(sys.modules, agent_runtime.base.__name__, None)
    agent_runtime.discover.return_value = []
    (tmp_path / "function_app.py").touch()
    runtime = ModuleType("azure_functions_runtime")
    monkeypatch.setitem(sys.modules, runtime.__name__, runtime)

    bridge._select_runtime(str(tmp_path))

    assert bridge._rt is runtime


def test_multiple_agent_runtimes_fail_before_loading(
        monkeypatch, agent_runtime):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")
    agent_runtime.discover.return_value.append(
        SimpleNamespace(name="other", load=Mock()))

    with pytest.raises(RuntimeError, match="Multiple runtimes detected"):
        bridge._select_runtime("")

    agent_runtime.entry_point.load.assert_not_called()
    assert bridge._rt is None


def test_entry_point_load_failure_is_not_silently_ignored(
        monkeypatch, agent_runtime):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")
    agent_runtime.entry_point.load.side_effect = ImportError("missing package")

    with pytest.raises(RuntimeError, match="Failed to load runtime entry point"):
        bridge._select_runtime("")

    assert bridge._rt is None


@pytest.mark.parametrize("base_state", ["missing", "old", "unregistered"])
def test_incompatible_or_unregistered_runtime_fails(
        monkeypatch, agent_runtime, base_state):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")
    if base_state == "missing":
        monkeypatch.setitem(sys.modules, agent_runtime.base.__name__, None)
    elif base_state == "old":
        del agent_runtime.base.RuntimeFeatureChecker
    else:
        agent_runtime.base.RuntimeFeatureChecker.runtime_loaded = lambda: False

    with pytest.raises(RuntimeError, match="Base extension version"):
        bridge._select_runtime("")


@pytest.mark.parametrize(
    "process_enabled,reload_enabled", [("0", "1"), ("1", "0")])
def test_reload_settings_override_process_runtime_gate(
        monkeypatch, tmp_path, agent_runtime, process_enabled, reload_enabled):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", process_enabled)
    (tmp_path / "function_app.py").touch()
    standard = ModuleType("azure_functions_runtime")
    monkeypatch.setitem(sys.modules, standard.__name__, standard)

    bridge._select_runtime(str(tmp_path), {
        "PYTHON_ENABLE_AGENT_RUNTIME": reload_enabled})

    expected = agent_runtime.runtime if reload_enabled == "1" else standard
    assert bridge._rt is expected


def test_specialization_selects_agent_and_resets_native_state(
        monkeypatch, tmp_path, agent_runtime):
    previous = SimpleNamespace(stop_threadpool_executor=Mock())
    monkeypatch.setattr(bridge, "_rt", previous)
    monkeypatch.setattr(bridge, "_native", object())
    monkeypatch.setattr(bridge, "_Datum", object())
    bridge._control_path_cache["old-function"] = False
    agent_runtime.runtime.start_threadpool_executor = Mock()
    agent_runtime.runtime.function_environment_reload_request = Mock()
    monkeypatch.setattr(bridge, "_run_coro", lambda result: None)

    bridge.handle_control("function_environment_reload_request", {
        "function_app_directory": str(tmp_path),
        "environment_variables": {"PYTHON_ENABLE_AGENT_RUNTIME": "1"},
    })

    assert bridge._rt is agent_runtime.runtime
    assert bridge._native is None
    assert bridge._Datum is None
    assert bridge._control_path_cache == {}
    previous.stop_threadpool_executor.assert_called_once_with()
    reload_handler = agent_runtime.runtime.function_environment_reload_request
    reload_handler.assert_called_once()
    agent_runtime.runtime.start_threadpool_executor.assert_called_once_with()


def test_agent_invocations_use_control_path_without_standard_registry(
        monkeypatch, agent_runtime):
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")
    bridge._select_runtime("")

    assert bridge.requires_control_path("fastapi-function") is True
    assert bridge._native is None


def test_worker_init_prioritizes_deps_before_standard_runtime_indexing(
        monkeypatch, tmp_path):
    deps = tmp_path / ".python_packages" / "lib" / "site-packages"
    deps.mkdir(parents=True)
    (tmp_path / "function_app.py").touch()
    runtime = sys.modules["azure_functions_runtime"]

    async def worker_init(request):
        assert sys.path[0] == str(deps)
        assert str(tmp_path) in sys.path

    runtime.worker_init_request = worker_init
    monkeypatch.setattr(bridge, "_run_coro", asyncio.run)
    bridge.configure("", "", "localhost")
    assert str(deps) not in sys.path

    bridge.handle_control("worker_init_request", {
        "function_app_directory": str(tmp_path)})

    assert bridge._rt is runtime


def test_worker_init_discovers_deployed_runtime_and_invokes_it(
        monkeypatch, tmp_path, agent_runtime):
    """Exercise real metadata discovery after configure's empty CLI app dir."""
    app_dir = tmp_path / "app"
    deps = app_dir / ".python_packages" / "lib" / "site-packages"
    dist = deps / "test_agent_runtime-1.0.dist-info"
    dist.mkdir(parents=True)
    (app_dir / "function_app.py").touch()
    (dist / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: test-agent-runtime\nVersion: 1.0\n",
        encoding="utf-8")
    (dist / "entry_points.txt").write_text(
        "[azurefunctions.runtimes]\nfastapi = test_agent_runtime:Runtime\n",
        encoding="utf-8")
    agent_runtime.runtime.Runtime = object()

    def deployed_entry_points(**kwargs):
        # Exercise real sys.path-based discovery, ignoring unrelated custom
        # runtimes that happen to be installed in the developer's environment.
        return [ep for ep in entry_points(**kwargs)
                if ep.dist.metadata["Name"] == "test-agent-runtime"]

    monkeypatch.setattr(bridge, "entry_points", deployed_entry_points)
    monkeypatch.setitem(sys.modules, "azure_functions_runtime_v1",
                        ModuleType("azure_functions_runtime_v1"))
    monkeypatch.setattr(bridge, "_run_coro", asyncio.run)

    async def worker_init(request):
        assert sys.path[0] == str(deps)
        assert request.properties["protos"] is bridge.protos
        return bridge.protos.WorkerInitResponse(
            result=bridge.protos.StatusResult(
                status=bridge.protos.StatusResult.Success))

    async def invocation(request):
        assert request.request.invocation_request.function_id == "fastapi"
        return bridge.protos.InvocationResponse(
            invocation_id="inv-1",
            return_value=bridge.protos.TypedData(string="hello"),
            result=bridge.protos.StatusResult(
                status=bridge.protos.StatusResult.Success))

    agent_runtime.runtime.worker_init_request = worker_init
    agent_runtime.runtime.invocation_request = invocation
    bridge.configure("", "", "localhost")
    monkeypatch.setenv("PYTHON_ENABLE_AGENT_RUNTIME", "1")

    response = bridge.handle_control("worker_init_request", {
        "function_app_directory": str(app_dir)})

    assert bridge._rt is agent_runtime.runtime
    assert response["result"]["status"] == bridge.protos.StatusResult.Success
    assert bridge.requires_control_path("fastapi") is True
    result = bridge.handle_invocation_control({
        "function_id": "fastapi", "invocation_id": "inv-1"})
    assert result["return_value"] == ("string", "hello")
