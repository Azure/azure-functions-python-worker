import os

from ..constants import (PYTHON_ROLLBACK_CWD_PATH,
                         PYTHON_THREADPOOL_THREAD_COUNT,
                         PYTHON_ISOLATE_WORKER_DEPENDENCIES,
                         PYTHON_ENABLE_WORKER_EXTENSIONS,
                         PYTHON_ENABLE_DEBUG_LOGGING,
                         FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED)


def get_python_appsetting_state():
    current_vars = os.environ.copy()
    python_specific_settings = \
        [PYTHON_ROLLBACK_CWD_PATH,
         PYTHON_THREADPOOL_THREAD_COUNT,
         PYTHON_ISOLATE_WORKER_DEPENDENCIES,
         PYTHON_ENABLE_DEBUG_LOGGING,
         FUNCTIONS_WORKER_SHARED_MEMORY_DATA_TRANSFER_ENABLED]

    app_setting_states = ""

    for app_setting in python_specific_settings:
        if app_setting in current_vars:
            app_setting_states += (app_setting + ": "
                                   + current_vars[app_setting] + " ")

    # Special case for extensions
    python_version = current_vars['FUNCTIONS_WORKER_RUNTIME_VERSION']
    if python_version == '3.9':
        app_setting_states += PYTHON_ENABLE_WORKER_EXTENSIONS + ": True "
    else:
        app_setting_states += PYTHON_ENABLE_WORKER_EXTENSIONS + ": False "

    return app_setting_states
