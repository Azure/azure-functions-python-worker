# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Any, Optional


# This represents the top level protos request sent from the host
class WorkerRequest:
    def __init__(self, name: str, request: Any, properties: dict):
        self.name = name
        self.request = request
        self.properties = properties


# This represents the inner request
class Request:
    def __init__(self, name: Any):
        self.worker_init_request = name
        self.function_load_request = name
        self.function_environment_reload_request = name


# This represents the Function Init/Metadata/Load/Invocation request
class FunctionRequest:
    def __init__(self, capabilities: Optional[Any] = {},
                 function_app_directory: Optional[Any] = "",
                 environment_variables: Optional[Any] = {},
                 function_id: Optional[Any] = "123",
                 metadata: Optional[Any] = {}):
        self.capabilities = capabilities
        self.function_app_directory = function_app_directory
        self.environment_variables = environment_variables
        self.function_id = function_id
        self.metadata = metadata


class Metadata:
    def __init__(self, name: str, directory: str, script_file: str, entry_point: str):
        self.name = name
        self.directory = directory
        self.script_file = script_file
        self.entry_point = entry_point


class MockHttpRequest:
    pass


class MockHttpResponse:
    pass
