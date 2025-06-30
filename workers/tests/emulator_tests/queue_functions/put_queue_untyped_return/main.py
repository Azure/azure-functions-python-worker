# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest) -> bytes:
    return azf.QueueMessage(body=req.get_body())
