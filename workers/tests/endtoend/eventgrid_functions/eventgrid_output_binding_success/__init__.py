# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func


def main(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')
