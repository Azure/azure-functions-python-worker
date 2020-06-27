# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest, msg: azf.Out[str]):
    msg.set(req.get_body())

    return 'OK'
