# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in ['1', 'true', 't', 'yes', 'y']


def is_envvar_true(env_key: str) -> bool:
    if os.getenv(env_key) is None:
        return False

    return is_true_like(os.environ[env_key])
