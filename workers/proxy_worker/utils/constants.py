# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# App Setting constants
PYTHON_ENABLE_DEBUG_LOGGING = "PYTHON_ENABLE_DEBUG_LOGGING"
PYTHON_THREADPOOL_THREAD_COUNT = "PYTHON_THREADPOOL_THREAD_COUNT"

# Container constants
CONTAINER_NAME = "CONTAINER_NAME"
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"

# new programming model default script file name
PYTHON_SCRIPT_FILE_NAME = "PYTHON_SCRIPT_FILE_NAME"
PYTHON_SCRIPT_FILE_NAME_DEFAULT = "function_app.py"

# EOL Dates
PYTHON_EOL_DATES = {
    '3.13': '2029-10',
    '3.14': '2030-10'
}

PYTHON_EOL_WARNING_DATES = {
    '3.13': '2029-04',
    '3.14': '2030-04'
}
