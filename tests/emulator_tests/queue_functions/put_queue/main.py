# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest, msg_snake: azf.Out[str]):
    msg_snake.set(req.get_body())

    return 'OK'
