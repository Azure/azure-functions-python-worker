# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions


def main(req: azure.functions.HttpRequest, context) -> str:
    return 'Hello World!'
