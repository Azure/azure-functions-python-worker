# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import importlib
import sys
import re
from types import ModuleType
import azure_functions_worker.utils.config_manager as config_manager

from azure_functions_worker.constants import CUSTOMER_PACKAGES_PATH, \
    PYTHON_EXTENSIONS_RELOAD_FUNCTIONS


def is_python_version(version: str) -> bool:
    current_version = f'{sys.version_info.major}.{sys.version_info.minor}'
    return current_version == version


def get_sdk_version(module: ModuleType) -> str:
    """Check the version of azure.functions sdk.

    Parameters
    ----------
    module: ModuleType
        The azure.functions SDK module

    Returns
    -------
    str
        The SDK version that our customer has installed.
    """

    return getattr(module, '__version__', 'undefined')


def get_sdk_from_sys_path() -> ModuleType:
    """Get the azure.functions SDK from the latest sys.path defined.
    This is to ensure the extension loaded from SDK coming from customer's
    site-packages.

    Returns
    -------
    ModuleType
        The azure.functions that is loaded from the first sys.path entry
    """

    if config_manager.is_envvar_true(PYTHON_EXTENSIONS_RELOAD_FUNCTIONS):
        backup_azure_functions = None
        backup_azure = None

        if 'azure.functions' in sys.modules:
            backup_azure_functions = sys.modules.pop('azure.functions')
        if 'azure' in sys.modules:
            backup_azure = sys.modules.pop('azure')

        module = importlib.import_module('azure.functions')

        if backup_azure:
            sys.modules['azure'] = backup_azure
        if backup_azure_functions:
            sys.modules['azure.functions'] = backup_azure_functions

        return module

    if CUSTOMER_PACKAGES_PATH not in sys.path:
        sys.path.insert(0, CUSTOMER_PACKAGES_PATH)

    return importlib.import_module('azure.functions')


class InvalidFileNameError(Exception):

    def __init__(self, file_name: str) -> None:
        super().__init__(
            f'Invalid file name: {file_name}')


def validate_script_file_name(file_name: str):
    # First character can be a letter, number, or underscore
    # Following characters can be a letter, number, underscore, hyphen, or dash
    # Ending must be .py
    pattern = re.compile(r'^[a-zA-Z0-9_][a-zA-Z0-9_\-]*\.py$')
    if not pattern.match(file_name):
        raise InvalidFileNameError(file_name)
    return True
