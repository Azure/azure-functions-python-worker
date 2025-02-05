import os
from typing import Callable, Optional

from .constants import (
    PYTHON_ENABLE_DEBUG_LOGGING,
    PYTHON_ENABLE_INIT_INDEXING,
    PYTHON_ENABLE_OPENTELEMETRY,
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_THREADPOOL_THREAD_COUNT,
)


def get_app_setting(
    setting: str,
    default_value: Optional[str] = None,
    validator: Optional[Callable[[str], bool]] = None
) -> Optional[str]:
    """Returns the application setting from environment variable.

    Parameters
    ----------
    setting: str
        The name of the application setting (e.g. FUNCTIONS_RUNTIME_VERSION)

    default_value: Optional[str]
        The expected return value when the application setting is not found,
        or the app setting does not pass the validator.

    validator: Optional[Callable[[str], bool]]
        A function accepts the app setting value and should return True when
        the app setting value is acceptable.

    Returns
    -------
    Optional[str]
        A string value that is set in the application setting
    """
    app_setting_value = os.getenv(setting)

    # If an app setting is not configured, we return the default value
    if app_setting_value is None:
        return default_value

    # If there's no validator, we should return the app setting value directly
    if validator is None:
        return app_setting_value

    # If the app setting is set with a validator,
    # On True, should return the app setting value
    # On False, should return the default value
    if validator(app_setting_value):
        return app_setting_value
    return default_value


def python_appsetting_state():
    current_vars = os.environ.copy()
    python_specific_settings = \
        [
         PYTHON_THREADPOOL_THREAD_COUNT,
         PYTHON_ENABLE_DEBUG_LOGGING,
         PYTHON_SCRIPT_FILE_NAME,
         PYTHON_ENABLE_INIT_INDEXING,
         PYTHON_ENABLE_OPENTELEMETRY]

    app_setting_states = "".join(
        f"{app_setting}: {current_vars[app_setting]} | "
        for app_setting in python_specific_settings
        if app_setting in current_vars
    )

    return app_setting_states
