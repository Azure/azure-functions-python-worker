# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from typing import Callable, Optional

from proxy_worker.utils.constants import (
    PYTHON_SCRIPT_FILE_NAME,
    PYTHON_SCRIPT_FILE_NAME_DEFAULT,
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


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {'1', 'true', 't', 'yes', 'y'}


def is_false_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {'0', 'false', 'f', 'no', 'n'}


def is_envvar_true(env_key: str) -> bool:
    if os.getenv(env_key) is None:
        return False

    return is_true_like(os.environ[env_key])


def is_envvar_false(env_key: str) -> bool:
    if os.getenv(env_key) is None:
        return False

    return is_false_like(os.environ[env_key])


def get_script_file_name():
    return get_app_setting(PYTHON_SCRIPT_FILE_NAME,
                           PYTHON_SCRIPT_FILE_NAME_DEFAULT)
