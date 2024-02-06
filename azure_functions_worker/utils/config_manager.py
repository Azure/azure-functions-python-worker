# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import yaml
from typing import Optional, Callable

config_data = {}


def read_config(function_path: str):
    with open(function_path, "r") as stream:
        try:
            global config_data
            # loads the entire yaml file
            config_data = yaml.safe_load(stream)
            # gets the python section of the yaml file
            config_data = config_data.get("PYTHON")
        except yaml.YAMLError as exc:
            print(exc)

    env_copy = os.environ
    # updates the config dictionary with the environment variables
    # this prioritizes set env variables over the config file
    config_data.update(env_copy)


def write_config(config_data: dict):
    with open("az-config.yml", "w") as stream:
        try:
            yaml.dump(config_data, stream)
        except yaml.YAMLError as exc:
            print(exc)


def config_exists() -> bool:
    return config_data is not {}


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {'1', 'true', 't', 'yes', 'y'}


def is_false_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in {'0', 'false', 'f', 'no', 'n'}


def is_envvar_true(key: str) -> bool:
    if config_exists() and config_data.get(key) is not None:
        return is_true_like(config_data.get(key))
    return False


def is_envvar_false(key: str) -> bool:
    if config_exists() and config_data.get(key) is not None:
        return is_false_like(config_data.get(key))
    return False


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
    if config_exists() and config_data.get(setting) is not None:
        # Setting exists, check with validator
        app_setting_value = config_data.get(setting)

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
    config_data.update({setting.lower: value})
