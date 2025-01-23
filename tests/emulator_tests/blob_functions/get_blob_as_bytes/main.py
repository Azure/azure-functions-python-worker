# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest, file_snake: bytes) -> str:
    assert isinstance(file_snake, bytes)
    return file_snake.decode('utf-8')
