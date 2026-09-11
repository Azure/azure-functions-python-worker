import sys
from pathlib import Path

from azure_functions_fastapi.loader import index_function_app_fastapi


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "modular_app"


def _is_fixture_module(module_name):
    return module_name == "function_app" or module_name == "app" or \
        module_name.startswith("app.")


def test_indexes_routes_registered_from_router_modules(monkeypatch):
    monkeypatch.chdir(FIXTURE_DIR)
    monkeypatch.syspath_prepend(str(FIXTURE_DIR))

    previous_modules = {
        module_name: sys.modules.pop(module_name)
        for module_name in list(sys.modules)
        if _is_fixture_module(module_name)
    }

    try:
        _, functions = index_function_app_fastapi(
            str(FIXTURE_DIR / "function_app.py"))

        indexed_routes = {
            (function.route_path, frozenset(function.http_methods))
            for function in functions
        }

        assert indexed_routes == {
            ("/", frozenset({"GET"})),
            ("/items/", frozenset({"GET"})),
            ("/items/", frozenset({"POST"})),
            ("/users/", frozenset({"POST"})),
            ("/users/{user_id}/profile/", frozenset({"GET"})),
        }
        assert all(
            function.function_script_file == "function_app.py"
            for function in functions
        )
        assert "app.routers.unregistered" not in sys.modules
        assert all(
            function.route_path != "/unregistered"
            for function in functions
        )
    finally:
        for module_name in list(sys.modules):
            if _is_fixture_module(module_name):
                sys.modules.pop(module_name)
        sys.modules.update(previous_modules)
