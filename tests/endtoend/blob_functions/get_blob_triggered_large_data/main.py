# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.InputStream) -> str:
    return file.read().decode('utf-8')
