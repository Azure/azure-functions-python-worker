import sys
import os
import json
import azure.functions as func
import google.protobuf as proto
import grpc

# Load dependency manager from customer' context
from azure_functions_worker.utils.dependency import DependencyManager as dm


def main(req: func.HttpRequest) -> func.HttpResponse:
    """This function is an HttpTrigger to check if the modules are loaded from
    customer's dependencies. We have mock a .python_packages/ folder in
    this e2e test function app which contains the following stub package:

    azure.functions==1.2.1
    protobuf==3.9.0
    grpc==1.35.0

    If the version we check is the same as the one in local .python_packages/,
    that means the isolate worker dependencies are working as expected.
    """
    result = {
        "sys.path": list(sys.path),
        "dependency_manager": {
            "cx_deps_path": dm._get_cx_deps_path(),
            "cx_working_dir": dm._get_cx_working_dir(),
            "worker_deps_path": dm._get_worker_deps_path(),
        },
        "libraries": {
            "func.expected.version": "1.2.1",
            "func.version": func.__version__,
            "func.file": func.__file__,
            "proto.expected.version": "3.9.0",
            "proto.version": proto.__version__,
            "proto.file": proto.__file__,
            "grpc.expected.version": "1.35.0",
            "grpc.version": grpc.__version__,
            "grpc.file": grpc.__file__,
        },
        "environments": {
            "PYTHON_ISOLATE_WORKER_DEPENDENCIES": (
                os.getenv('PYTHON_ISOLATE_WORKER_DEPENDENCIES')
            ),
            "AzureWebJobsScriptRoot": os.getenv('AzureWebJobsScriptRoot'),
            "PYTHONPATH": os.getenv('PYTHONPATH'),
            "HOST_VERSION": os.getenv('HOST_VERSION')
        }
    }
    return func.HttpResponse(json.dumps(result))
