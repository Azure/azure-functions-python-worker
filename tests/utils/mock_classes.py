# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Any, List, Optional


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
        self.function_environment_reload_request = name


# This represents the Function Init/Metadata/Load/Invocation request
class FunctionRequest:
    def __init__(self, capabilities: Any,
                 function_app_directory: Any,
                 environment_variables: Optional[Any] = None):
        self.capabilities = capabilities
        self.function_app_directory = function_app_directory
        self.environment_variables = environment_variables


class MockMBD:
    def __init__(self, version: str, source: str,
                 content_type: str, content: str):
        self.version = version
        self.source = source
        self.content_type = content_type
        self.content = content


class MockCMBD:
    def __init__(self, model_binding_data: List[MockMBD]):
        self.model_binding_data = model_binding_data


class MockHttpRequest:
    pass


class MockHttpResponse:
    pass
