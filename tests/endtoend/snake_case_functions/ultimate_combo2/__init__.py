# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# flake8: noqa
import logging

import azure.functions as func


def main(__9req__snake__sna_ke________snake__sn0ke_: func.HttpRequest) -> func.HttpResponse:
    name = __9req__snake__sna_ke________snake__sn0ke_.params.get('name')
    return func.HttpResponse(f"Hello, {name}.")
