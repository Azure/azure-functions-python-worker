# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import io

import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.Out[io.StringIO]) -> str:
    file.set(io.StringIO('filelike'))
    return 'OK'
