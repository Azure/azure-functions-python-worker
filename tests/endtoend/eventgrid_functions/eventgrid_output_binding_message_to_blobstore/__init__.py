# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func


def main(msg: func.QueueMessage) -> bytes:
    return msg.get_body()
