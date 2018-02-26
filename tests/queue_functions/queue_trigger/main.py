import json

import azure.functions as azf


def main(msg: azf.QueueMessage) -> str:
    result = json.dumps({
        'id': msg.id,
        'body': msg.get_body().decode('utf-8'),
        'expiration_time': (msg.expiration_time.isoformat()
                            if msg.expiration_time else None),
        'insertion_time': (msg.insertion_time.isoformat()
                           if msg.insertion_time else None),
        'next_visible_time': (msg.next_visible_time.isoformat()
                              if msg.next_visible_time else None),
        'pop_receipt': msg.pop_receipt,
        'dequeue_count': msg.dequeue_count
    })

    return result
