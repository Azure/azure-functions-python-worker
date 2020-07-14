# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import typing
import json
import azure.functions as func


# This is an actual EventHub trigger which handles Eventhub events in batches.
# It serializes multiple event data into a json and store it into a blob.
def main(events: typing.List[func.EventHubEvent]) -> bytes:
    event_list = []
    for event in events:
        event_dict: typing.Mapping[str, typing.Any] = {
            'body': event.get_body().decode('utf-8'),
            'enqueued_time': event.enqueued_time.isoformat(),
            'partition_key': event.partition_key,
            'sequence_number': event.sequence_number,
            'offset': event.offset,
            'metadata': event.metadata
        }
        event_list.append(event_dict)

    return json.dumps(event_list)
