# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# TODO: organize this better

import sys

TRUE = "true"
TRACEPARENT = "traceparent"
TRACESTATE = "tracestate"

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
PYTHON_THREADPOOL_THREAD_COUNT = "PYTHON_THREADPOOL_THREAD_COUNT"
PYTHON_ENABLE_DEBUG_LOGGING = "PYTHON_ENABLE_DEBUG_LOGGING"

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

# Setting Defaults
PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT = 1
PYTHON_THREADPOOL_THREAD_COUNT_MIN = 1
PYTHON_THREADPOOL_THREAD_COUNT_MAX = sys.maxsize
PYTHON_THREADPOOL_THREAD_COUNT_MAX_37 = 32
PYTHON_ENABLE_OPENTELEMETRY_DEFAULT = False
PYTHON_AZURE_MONITOR_LOGGER_NAME_DEFAULT = ""

# External Site URLs
MODULE_NOT_FOUND_TS_URL = "https://aka.ms/functions-modulenotfound"

PYTHON_LANGUAGE_RUNTIME = "python"

# Paths
CUSTOMER_PACKAGES_PATH = "/home/site/wwwroot/.python_packages/lib/site" \
                         "-packages"

METADATA_PROPERTIES_WORKER_INDEXED = "worker_indexed"

# Header names
X_MS_INVOCATION_ID = "x-ms-invocation-id"

# Trigger Names
HTTP_TRIGGER = "httpTrigger"

# Output Names
HTTP = "http"

# Appsetting to specify AppInsights connection string
APPLICATIONINSIGHTS_CONNECTION_STRING = "APPLICATIONINSIGHTS_CONNECTION_STRING"
