# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(msg: azf.QueueMessage) -> bytes:
    return msg.get_body()
