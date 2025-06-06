# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging

import azure.functions as func


def main(req_snake: func.HttpRequest) -> func.HttpResponse:
    name = req_snake.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
