# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func


def main(event: func.EventGridEvent) -> str:
    return json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
        'event_time': (event.event_time.isoformat() if
                       event.event_time else None),
        'data_version': event.data_version
    })
