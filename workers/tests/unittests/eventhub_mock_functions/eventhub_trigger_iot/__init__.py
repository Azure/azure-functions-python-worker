# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func


def main(event: func.EventHubEvent) -> str:
    return json.dumps(event.iothub_metadata)
