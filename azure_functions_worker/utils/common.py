# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Optional
import os


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in ['1', 'true', 't', 'yes', 'y']


def is_envvar_true(env_key: str) -> bool:
    if os.getenv(env_key) is None:
        return False

    return is_true_like(os.environ[env_key])


def get_app_setting(setting: str,
                    default_value: Optional[str] = None) -> Optional[str]:
    """Returns the application setting from environment variable.

    Parameters
    ----------
    setting: str
        The name of the application setting (e.g. FUNCTIONS_RUNTIME_VERSION)
    default_value: Optional[str]
        The expected return value when the application setting is not found.

    Returns
    -------
    Optional[str]
        A string value that is set in the application setting
    """
    app_setting_value = os.getenv(setting)

    if app_setting_value is None:
        return default_value

    return app_setting_value
