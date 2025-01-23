# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func


def main(event_snake: func.EventGridEvent) -> str:
    return json.dumps({
        'id': event_snake.id,
        'data': event_snake.get_json(),
        'topic': event_snake.topic,
        'subject': event_snake.subject,
        'event_type': event_snake.event_type,
    })
