# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import typing
import json
import azure.functions as func


# This is an actual EventHub trigger. It picks a few of EventHub properties
# and converts them into a storage blob
async def main(event: func.EventHubEvent) -> bytes:
    event_dict: typing.Mapping[str, typing.Any] = {
        'body': event.get_body().decode('utf-8'),
        # Uncomment this when the EnqueuedTimeUtc is fixed in azure-functions
        # 'enqueued_time': event.enqueued_time.isoformat(),
        'partition_key': event.partition_key,
        'sequence_number': event.sequence_number,
        'offset': event.offset,
        'metadata': event.metadata
    }

    return json.dumps(event_dict)
