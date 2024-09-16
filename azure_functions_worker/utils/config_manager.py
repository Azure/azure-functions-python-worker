# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import json
from typing import Optional, Callable, Dict


class ConfigManager(object):
    """
    // TODO: docs here
    """
    def __init__(self):
        """
        // TODO: docs here
        """
        self.config_data: Optional[Dict[str, str]] = None

    def read_config(self, function_path: str):
        if self.config_data is None:
            self.config_data = {}
        try:
            with open(function_path, "r") as stream:
                # loads the entire json file
                full_config_data = json.load(stream)
                # gets the python section of the json file
                self.config_data = full_config_data.get("PYTHON")
        except FileNotFoundError:
            pass

        # updates the config dictionary with the environment variables
        # this prioritizes set env variables over the config file
        env_copy = os.environ
        for k, v in env_copy.items():
            self.config_data.update({k.upper(): v})

    def config_exists(self) -> bool:
        if self.config_data is None:
            self.read_config("")
        return self.config_data is not None

    def get_config(self) -> dict:
        return self.config_data

    def is_true_like(self, setting: str) -> bool:
        if setting is None:
            return False

        return setting.lower().strip() in {"1", "true", "t", "yes", "y"}

    def is_false_like(self, setting: str) -> bool:
        if setting is None:
            return False

        return setting.lower().strip() in {"0", "false", "f", "no", "n"}

    def is_envvar_true(self, key: str) -> bool:
        key_upper = key.upper()
        # special case for PYTHON_ENABLE_DEBUG_LOGGING
        # This is read by the host and must be set in os.environ
        if key_upper == "PYTHON_ENABLE_DEBUG_LOGGING":
            val = os.getenv(key_upper)
            return self.is_true_like(val)
        if self.config_exists() and not self.config_data.get(key_upper):
            return False
        return self.is_true_like(self.config_data.get(key_upper))

    def is_envvar_false(self, key: str) -> bool:
        key_upper = key.upper()
        if self.config_exists() and not self.config_data.get(key_upper):
            return False
        return self.is_false_like(self.config_data.get(key_upper))

    def get_app_setting(
            self,
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
        if self.config_exists() and self.config_data.get(setting_upper) is not None:
            # Setting exists, check with validator
            app_setting_value = self.config_data.get(setting_upper)

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

    def set_env_var(self, setting: str, value: str):
        self.config_data[setting] = value

    def del_env_var(self, setting: str):
        self.config_data.pop(setting, None)

    def clear_config(self):
        if self.config_data is not None:
            self.config_data.clear()
            self.config_data = None


config_manager = ConfigManager()
