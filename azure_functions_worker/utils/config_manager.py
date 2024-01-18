# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import yaml
from typing import Optional, Callable

config_data = {}

def read_config(function_path: str) -> dict:
    with open(function_path, "r") as stream:
        try:
            global config_data
            config_data = yaml.safe_load(stream)
            config_data = dict((k, v) for k,v in config_data.items())
        except yaml.YAMLError as exc:
            print(exc)
    return config_data


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
    if config_data.get(key) is None:
        return False
    
    return is_true_like(config_data.get(key))


def is_envvar_false(key: str) -> bool:
    if config_data.get(key) is None:
        return False
    
    return is_false_like(config_data.get(key))


def get_env_var(
    setting: str, 
    default_value: Optional[str] = None,
    validator: Optional[Callable[[str], bool]] = None
) -> Optional[str]:
    app_setting_value = config_data.get(setting)

    if app_setting_value is None:
        return default_value
    
    if validator is None:
        return app_setting_value
    
    if validator(app_setting_value):
        return app_setting_value
    return default_value


def set_env_var(setting: str, value: str):
    config_data.update({setting.lower: value})