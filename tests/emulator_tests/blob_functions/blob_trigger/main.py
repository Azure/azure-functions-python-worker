# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as azf


def main(file_snake: azf.InputStream) -> str:
    return json.dumps({
        'name': file_snake.name,
        'length': file_snake.length,
        'content': file_snake.read().decode('utf-8')
    })
