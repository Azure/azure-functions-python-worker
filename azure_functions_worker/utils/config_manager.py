# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import json
from typing import Optional, Callable, Dict

# Initialize to None
config_data: Optional[Dict[str, str]] = None


def read_config(function_path: str):
    global config_data
    if config_data is None:
        config_data = {}
    try:
        with open(function_path, "r") as stream:
            # loads the entire json file
            full_config_data = json.load(stream)
            # gets the python section of the json file
            config_data = full_config_data.get("PYTHON")
    except FileNotFoundError:
        pass

        # updates the config dictionary with the environment variables
    # this prioritizes set env variables over the config file
    env_copy = os.environ
    for k, v in env_copy.items():
        config_data.update({k.upper(): v})


def config_exists() -> bool:
    global config_data
    if config_data is None:
        read_config("")
    return config_data is not None


def get_config() -> dict:
    return config_data


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {"1", "true", "t", "yes", "y"}


def is_false_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {"0", "false", "f", "no", "n"}


def is_envvar_true(key: str) -> bool:
    key_upper = key.upper()
    # special case for PYTHON_ENABLE_DEBUG_LOGGING
    # This is read by the host and must be set in os.environ
    if key_upper == "PYTHON_ENABLE_DEBUG_LOGGING":
        val = os.getenv(key_upper)
        return is_true_like(val)
    if config_exists() and not config_data.get(key_upper):
        return False
    return is_true_like(config_data.get(key_upper))


def is_envvar_false(key: str) -> bool:
    key_upper = key.upper()
    if config_exists() and not config_data.get(key_upper):
        return False
    return is_false_like(config_data.get(key_upper))


def get_app_setting(
    setting: str,
    default_value: Optional[str] = None,
    validator: Optional[Callable[[str], bool]] = None,
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
    setting_upper = setting.upper()
    if config_exists() and config_data.get(setting_upper) is not None:
        # Setting exists, check with validator
        app_setting_value = config_data.get(setting_upper)

        # If there's no validator, return the app setting value directly
        if validator is None:
            return app_setting_value

        # If the app setting is set with a validator,
        # On True, should return the app setting value
        # On False, should return the default value
        if validator(app_setting_value):
            return app_setting_value

    # Setting is not configured or validator is false
    # Return default value
    return default_value


def set_env_var(setting: str, value: str):
    global config_data
    config_data[setting] = value


def del_env_var(setting: str):
    global config_data
    config_data.pop(setting, None)


def clear_config():
    global config_data
    if config_data is not None:
        config_data.clear()
        config_data = None
