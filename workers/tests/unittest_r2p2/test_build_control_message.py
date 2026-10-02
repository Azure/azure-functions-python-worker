# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Unit tests for ``bridge._build_control_message`` -- the pure shaping of Rust's
# decoded request dict into the ``request.request.<type>`` attribute object the
# (unchanged) runtime handlers read. The returned object mirrors that shape: the
# outer namespace exposes the message under an attribute named for the request
# type (e.g. ``.worker_init_request``). No runtime or Rust binary required.

import bridge


def test_worker_init_request_shape():
    outer = bridge._build_control_message(
        "worker_init_request",
        {
            "capabilities": {"RawHttpBodyBytes": "true"},
            "function_app_directory": "/home/site/wwwroot",
            "host_version": "4.1.0",
        },
    )
    msg = outer.worker_init_request
    assert msg.capabilities == {"RawHttpBodyBytes": "true"}
    assert msg.function_app_directory == "/home/site/wwwroot"
    assert msg.host_version == "4.1.0"


def test_worker_init_request_defaults_are_empty():
    msg = bridge._build_control_message(
        "worker_init_request", {}
    ).worker_init_request
    assert msg.capabilities == {}
    assert msg.function_app_directory == ""
    assert msg.host_version == ""


def test_functions_metadata_request_is_empty_namespace():
    outer = bridge._build_control_message("functions_metadata_request", {})
    assert outer is not None
    # No fields -- the runtime metadata handler reads nothing off the request.
    assert not vars(outer.functions_metadata_request)


def test_function_load_request_shape_with_bindings():
    msg = bridge._build_control_message(
        "function_load_request",
        {
            "function_id": "fid-1",
            "metadata": {
                "name": "hello",
                "entry_point": "main",
                "bindings": {
                    "req": {"type": "httpTrigger", "direction": 0,
                            "data_type": 0},
                },
            },
        },
    ).function_load_request
    assert msg.function_id == "fid-1"
    assert msg.metadata.name == "hello"
    assert msg.metadata.entry_point == "main"
    assert msg.metadata.bindings["req"].type == "httpTrigger"
    assert msg.metadata.bindings["req"].direction == 0


def test_function_load_request_without_metadata():
    msg = bridge._build_control_message(
        "function_load_request", {"function_id": "fid-2"}
    ).function_load_request
    assert msg.function_id == "fid-2"
    assert msg.metadata is None


def test_env_reload_request_shape():
    msg = bridge._build_control_message(
        "function_environment_reload_request",
        {
            "function_app_directory": "/home/site/wwwroot",
            "environment_variables": {"A": "1", "B": "2"},
        },
    ).function_environment_reload_request
    assert msg.function_app_directory == "/home/site/wwwroot"
    assert msg.environment_variables == {"A": "1", "B": "2"}


def test_unknown_request_returns_none():
    assert bridge._build_control_message("bogus_request", {}) is None
