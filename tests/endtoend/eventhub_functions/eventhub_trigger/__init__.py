# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(event: func.EventHubEvent) -> bytes:
    return event.get_body()
