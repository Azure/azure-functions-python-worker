import json

import azure.functions as func


def main(event: func.EventGridEvent) -> str:
    result = json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })

    return result
