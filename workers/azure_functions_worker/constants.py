# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys

# Capabilities
RAW_HTTP_BODY_BYTES = "RawHttpBodyBytes"
TYPED_DATA_COLLECTION = "TypedDataCollection"
RPC_HTTP_BODY_ONLY = "RpcHttpBodyOnly"
RPC_HTTP_TRIGGER_METADATA_REMOVED = "RpcHttpTriggerMetadataRemoved"
WORKER_STATUS = "WorkerStatus"
SHARED_MEMORY_DATA_TRANSFER = "SharedMemoryDataTransfer"
FUNCTION_DATA_CACHE = "FunctionDataCache"
HTTP_URI = "HttpUri"
REQUIRES_ROUTE_PARAMETERS = "RequiresRouteParameters"
# When this capability is enabled, logs are not piped back to the
# host from the worker. Logs will directly go to where the user has
# configured them to go. This is to ensure that the logs are not
# duplicated.
WORKER_OPEN_TELEMETRY_ENABLED = "WorkerOpenTelemetryEnabled"

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
PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT = 1
PYTHON_THREADPOOL_THREAD_COUNT_MIN = 1
PYTHON_THREADPOOL_THREAD_COUNT_MAX = sys.maxsize
PYTHON_THREADPOOL_THREAD_COUNT_MAX_37 = 32

PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT = False
PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_310 = False
PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT = False
PYTHON_ENABLE_WORKER_EXTENSIONS_DEFAULT_39 = True

# new programming model default script file name
PYTHON_SCRIPT_FILE_NAME = "PYTHON_SCRIPT_FILE_NAME"
PYTHON_SCRIPT_FILE_NAME_DEFAULT = "function_app.py"

# External Site URLs
MODULE_NOT_FOUND_TS_URL = "https://aka.ms/functions-modulenotfound"

PYTHON_LANGUAGE_RUNTIME = "python"

# Settings for V2 programming model
RETRY_POLICY = "retry_policy"

# Paths
CUSTOMER_PACKAGES_PATH = "/home/site/wwwroot/.python_packages/lib/site" \
                         "-packages"

# Flag to index functions in handle init request
PYTHON_ENABLE_INIT_INDEXING = "PYTHON_ENABLE_INIT_INDEXING"

METADATA_PROPERTIES_WORKER_INDEXED = "worker_indexed"

# Header names
X_MS_INVOCATION_ID = "x-ms-invocation-id"

# Trigger Names
HTTP_TRIGGER = "httpTrigger"

# Output Names
HTTP = "http"

# Base extension supported Python minor version
BASE_EXT_SUPPORTED_PY_MINOR_VERSION = 8

# Appsetting to turn on OpenTelemetry support/features
# A value of "true" enables the setting
PYTHON_ENABLE_OPENTELEMETRY = "PYTHON_ENABLE_OPENTELEMETRY"

# Appsetting to turn on ApplicationInsights support/features
# A value of "true" enables the setting
PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY = \
    "PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY"

# Appsetting to specify root logger name of logger to collect telemetry for
# Used by Azure monitor distro (Application Insights)
PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME = "PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME"
PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME_DEFAULT = ""

# Appsetting to specify AppInsights connection string
APPLICATIONINSIGHTS_CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"

# EOL Dates
PYTHON_EOL_DATES = {
    '3.7': '2023-10',
    '3.8': '2024-10',
    '3.9': '2025-10',
    '3.10': '2026-10',
    '3.11': '2027-10',
    '3.12': '2028-10'
}

PYTHON_EOL_WARNING_DATES = {
    '3.7': '2023-04',
    '3.8': '2024-04',
    '3.9': '2025-04',
    '3.10': '2026-04',
    '3.11': '2027-04',
    '3.12': '2028-04'
}

# Service Bus Client Name
SERVICE_BUS_CLIENT_NAME = "serviceBusClient"
