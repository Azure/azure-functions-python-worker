# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging

import azure.functions as func


def main(__main__: func.HttpRequest) -> func.HttpResponse:
    name = __main__.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
