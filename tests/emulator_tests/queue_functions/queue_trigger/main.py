# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as azf


def main(msg_snake: azf.QueueMessage) -> str:
    result = json.dumps({
        'id': msg_snake.id,
        'body': msg_snake.get_body().decode('utf-8'),
        'expiration_time': (msg_snake.expiration_time.isoformat()
                            if msg_snake.expiration_time else None),
        'insertion_time': (msg_snake.insertion_time.isoformat()
                           if msg_snake.insertion_time else None),
        'time_next_visible': (msg_snake.time_next_visible.isoformat()
                              if msg_snake.time_next_visible else None),
        'pop_receipt': msg_snake.pop_receipt,
        'dequeue_count': msg_snake.dequeue_count
    })

    return result
