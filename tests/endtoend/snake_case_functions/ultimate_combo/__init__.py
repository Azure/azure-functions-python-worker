# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging

import azure.functions as func


def main(_req_snake_snake_snake_snake_: func.HttpRequest) -> func.HttpResponse:
    name = _req_snake_snake_snake_snake_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
