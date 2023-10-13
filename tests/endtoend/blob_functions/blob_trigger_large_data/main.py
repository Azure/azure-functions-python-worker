# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as azf


def main(file: azf.InputStream) -> str:
    return json.dumps({
        'name': file.name,
        'length': file.length,
        'content': file.read().decode('utf-8')
    })
