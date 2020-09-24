# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# Prefixes
CONSOLE_LOG_PREFIX = "LanguageWorkerConsoleLog"

# Capabilities
RAW_HTTP_BODY_BYTES = "RawHttpBodyBytes"
TYPED_DATA_COLLECTION = "TypedDataCollection"
RPC_HTTP_BODY_ONLY = "RpcHttpBodyOnly"
RPC_HTTP_TRIGGER_METADATA_REMOVED = "RpcHttpTriggerMetadataRemoved"

# Debug Flags
PYAZURE_WEBHOST_DEBUG = "PYAZURE_WEBHOST_DEBUG"

# Python Specific Feature Flags and App Settings
PYTHON_ROLLBACK_CWD_PATH = "PYTHON_ROLLBACK_CWD_PATH"
PYTHON_THREADPOOL_THREAD_COUNT = "PYTHON_THREADPOOL_THREAD_COUNT"

# Setting Defaults
PYTHON_THREADPOOL_THREAD_COUNT_DEFAULT = 1
PYTHON_THREADPOOL_THREAD_COUNT_MIN = 1
PYTHON_THREADPOOL_THREAD_COUNT_MAX = 32

# External Site URLs
MODULE_NOT_FOUND_TS_URL = "https://aka.ms/functions-modulenotfound"
