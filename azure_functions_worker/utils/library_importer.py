# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

"""
File to import library dependencies.
This file should be used to import any dependency from the library since
directly importing azure.functions may cause ModuleNotFound error is the user
has pinned their azure.functions to an older release version.

"""


def get_azure_function():
    try:
        from azure.functions import Function as func
        return func
    except ImportError:
        logging.error("azure.functions is pinned to an older version. "
                      "Please pin azure.functions to version 1.10.1 or higher")


def get_azure_function_app():
    try:
        from azure.functions import FunctionApp as funcApp
        return funcApp
    except ImportError:
        logging.error("azure.functions is pinned to an older version. "
                      "Please pin azure.functions to version 1.10.1 or higher")


Function = get_azure_function()
FunctionApp = get_azure_function_app()
