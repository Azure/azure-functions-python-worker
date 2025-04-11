# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os

from .constants import (
    FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED,
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_ENABLE_OPENTELEMETRY,
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_THREADPOOL_THREAD_COUNT,
)


def get_python_appsetting_state():
    current_vars = os.environ.copy()
    python_specific_settings = \
        [PYTHON_THREADPOOL_THREAD_COUNT,
         PYTHON_ENABLE_DEBUG_LOGGING,
         FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED,
         PYTHON_SCRIPT_FILE_NAME,
         PYTHON_ENABLE_OPENTELEMETRY]

    app_setting_states = "".join(
        f"{app_setting}: {current_vars[app_setting]} | "
        for app_setting in python_specific_settings
        if app_setting in current_vars
    )

    return app_setting_states
