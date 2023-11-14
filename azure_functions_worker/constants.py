# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import sys

# Capabilities
RAW_HTTP_BODY_BYTES = "RawHttpBodyBytes"
TYPED_DATA_COLLECTION = "TypedDataCollection"
RPC_HTTP_BODY_ONLY = "RpcHttpBodyOnly"
RPC_HTTP_TRIGGER_METADATA_REMOVED = "RpcHttpTriggerMetadataRemoved"
WORKER_STATUS = "WorkerStatus"
SHARED_MEMORY_DATA_TRANSFER = "SharedMemoryDataTransfer"
FUNCTION_DATA_CACHE = "FunctionDataCache"

# Platform Environment Variables
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"
CONTAINER_NAME = "CONTAINER_NAME"

# Python Specific Feature Flags and App Settings
PYTHON_ROLLBACK_CWD_PATH = "PYTHON_ROLLBACK_CWD_PATH"
PYTHON_THREADPOOL_THREAD_COUNT = "PYTHON_THREADPOOL_THREAD_COUNT"
PYTHON_ISOLATE_WORKER_DEPENDENCIES = "PYTHON_ISOLATE_WORKER_DEPENDENCIES"
PYTHON_ENABLE_WORKER_EXTENSIONS = "PYTHON_ENABLE_WORKER_EXTENSIONS"
PYTHON_ENABLE_DEBUG_LOGGING = "PYTHON_ENABLE_DEBUG_LOGGING"
FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED = \
    "FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED"
"""
Comma-separated list of directories where shared memory maps can be created for
data transfer between host and worker.
"""
UNIX_SHARED_MEMORY_DIRECTORIES = "FUNCTIONS_UNIX_SHARED_MEMORY_DIRECTORIES"

# Setting Defaults
PYTHON_ROLLBACK_CWD_PATH_DEFAULT = False
PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT = 1
PYTHON_THREADPOOL_THREAD_COUNT_MIN = 1
PYTHON_THREADPOOL_THREAD_COUNT_MAX = sys.maxsize
PYTHON_THREADPOOL_THREAD_COUNT_MAX_37 = 32

PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT = False
PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_310 = False
PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT = False
PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39 = True
PYTHON_ENABLE_DEBUG_LOGGING_DEFAULT = False
FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED_DEFAULT = False
PYTHON_EXTENSIONS_RELOAD_FUNCTIONS = "PYTHON_EXTENSIONS_RELOAD_FUNCTIONS"

# External Site URLs
MODULE_NOT_FOUND_TS_URL = "https://aka.ms/functions-modulenotfound"

# new programming model script file name
SCRIPT_FILE_NAME = "function_app.py"
PYTHON_LANGUAGE_RUNTIME = "python"

# Settings for V2 programming model
RETRY_POLICY = "retry_policy"

# Paths
CUSTOMER_PACKAGES_PATH = "/home/site/wwwroot/.python_packages/lib/site-packages"


def get_python_appsetting_state():
    app_settings = {
        "PYTHON_ROLLBACK_CWD_PATH":
        get_statement(PYTHON_ROLLBACK_CWD_PATH,
                      PYTHON_ROLLBACK_CWD_PATH_DEFAULT),
        "PYTHON_THREADPOOL_THREAD_COUNT":
        get_statement(PYTHON_THREADPOOL_THREAD_COUNT,
                      PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT),
        "PYTHON_ISOLATE_WORKER_DEPENDENCIES":
        get_statement(PYTHON_ISOLATE_WORKER_DEPENDENCIES,
                      PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT),
        "PYTHON_ENABLE_WORKER_EXTENSIONS":
        get_statement(PYTHON_ENABLE_WORKER_EXTENSIONS,
                      PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT),
            "PYTHON_ENABLE_DEBUG_LOGGING":
        get_statement(PYTHON_ENABLE_DEBUG_LOGGING,
                      PYTHON_ENABLE_DEBUG_LOGGING_DEFAULT),
        "FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED":
        get_statement(FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED,
                      "False")
    }

    return str(app_settings)


def get_statement(app_setting, default_value):
    app_setting_state = os.getenv(app_setting)

    if app_setting_state is None:
        app_setting_state = str(default_value)

    if app_setting in os.environ:
        return "set to " + app_setting_state + " by customer"
    else:
        return "set to " + app_setting_state + " by default"
