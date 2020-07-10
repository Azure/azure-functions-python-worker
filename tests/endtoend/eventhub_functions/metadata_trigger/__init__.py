# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import typing
import json
import azure.functions as func


def main(event: func.EventHubEvent) -> bytes:
    event_dict: typing.Mapping[str, typing.Any] = {
        'body': event.get_body().decode('utf-8'),
        'enqueued_time': event.enqueued_time,
        'partition_key': event.partition_key,
        'sequence_number': event.sequence_number,
        'offset': event.offset,
        'metadata': event.metadata
    }

    return json.dumps(event_dict)
