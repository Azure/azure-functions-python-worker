# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import sys

# Constants for Azure Functions Python Worker
CUSTOMER_PACKAGES_PATH = "/home/site/wwwroot/.python_packages/lib/site" \
                         "-packages"
HTTP = "http"
HTTP_TRIGGER = "httpTrigger"
METADATA_PROPERTIES_WORKER_INDEXED = "worker_indexed"
MODULE_NOT_FOUND_TS_URL = "https://aka.ms/functions-modulenotfound"
PYTHON_LANGUAGE_RUNTIME = "python"
RETRY_POLICY = "retry_policy"
SERVICE_BUS_CLIENT_NAME = "serviceBusClient"
TRUE = "true"
TRACEPARENT = "traceparent"
TRACESTATE = "tracestate"
X_MS_INVOCATION_ID = "x-ms-invocation-id"


# Capabilities
FUNCTION_DATA_CACHE = "FunctionDataCache"
HTTP_URI = "HttpUri"
RAW_HTTP_BODY_BYTES = "RawHttpBodyBytes"
REQUIRES_ROUTE_PARAMETERS = "RequiresRouteParameters"
RPC_HTTP_BODY_ONLY = "RpcHttpBodyOnly"
RPC_HTTP_TRIGGER_METADATA_REMOVED = "RpcHttpTriggerMetadataRemoved"
SHARED_MEMORY_DATA_TRANSFER = "SharedMemoryDataTransfer"
TYPED_DATA_COLLECTION = "TypedDataCollection"
# When this capability is enabled, logs are not piped back to the
# host from the worker. Logs will directly go to where the user has
# configured them to go. This is to ensure that the logs are not
# duplicated.
WORKER_OPEN_TELEMETRY_ENABLED = "WorkerOpenTelemetryEnabled"
WORKER_STATUS = "WorkerStatus"


# Platform Environment Variables
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"
CONTAINER_NAME = "CONTAINER_NAME"


# Python Specific Feature Flags and App Settings
# Appsetting to specify AppInsights connection string
APPLICATIONINSIGHTS_CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"
# Appsetting to turn on ApplicationInsights support/features
# A value of "true" enables the setting
PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY = \
    "PYTHON_APPLICATIONINSIGHTS_ENABLE_TELEMETRY"
# Appsetting to specify root logger name of logger to collect telemetry for
# Used by Azure monitor distro (Application Insights)
PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME = "PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME"
PYTHON_APPLICATIONINSIGHTS_LOGGER_NAME_DEFAULT = ""
PYTHON_ENABLE_DEBUG_LOGGING = "PYTHON_ENABLE_DEBUG_LOGGING"
# Appsetting to turn on OpenTelemetry support/features
# A value of "true" enables the setting
PYTHON_ENABLE_OPENTELEMETRY = "PYTHON_ENABLE_OPENTELEMETRY"
# Allows for non-default script file name
PYTHON_SCRIPT_FILE_NAME = "PYTHON_SCRIPT_FILE_NAME"
PYTHON_SCRIPT_FILE_NAME_DEFAULT = "function_app.py"
PYTHON_THREADPOOL_THREAD_COUNT = "PYTHON_THREADPOOL_THREAD_COUNT"
PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT = 1
PYTHON_THREADPOOL_THREAD_COUNT_MAX = sys.maxsize
PYTHON_THREADPOOL_THREAD_COUNT_MIN = 1
