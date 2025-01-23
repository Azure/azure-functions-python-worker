# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# This is an actual EventHub trigger which will convert the event data
# into a storage blob.
def main(event_snake: func.EventHubEvent) -> bytes:
    return event_snake.get_body()
