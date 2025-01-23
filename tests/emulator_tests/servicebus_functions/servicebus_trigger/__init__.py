# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as azf


def main(msg_snake: azf.ServiceBusMessage) -> str:
    result = json.dumps({
        'message_id': msg_snake.message_id,
        'body': msg_snake.get_body().decode('utf-8'),
        'content_type': msg_snake.content_type,
        'delivery_count': msg_snake.delivery_count,
        'expiration_time': (msg_snake.expiration_time.isoformat() if
                            msg_snake.expiration_time else None),
        'label': msg_snake.label,
        'partition_key': msg_snake.partition_key,
        'reply_to': msg_snake.reply_to,
        'reply_to_session_id': msg_snake.reply_to_session_id,
        'scheduled_enqueue_time': (msg_snake.scheduled_enqueue_time.isoformat() if
                                   msg_snake.scheduled_enqueue_time else None),
        'session_id': msg_snake.session_id,
        'time_to_live': msg_snake.time_to_live,
        'to': msg_snake.to,
        'user_properties': msg_snake.user_properties,

        'application_properties': msg_snake.application_properties,
        'correlation_id': msg_snake.correlation_id,
        'dead_letter_error_description': msg_snake.dead_letter_error_description,
        'dead_letter_reason': msg_snake.dead_letter_reason,
        'dead_letter_source': msg_snake.dead_letter_source,
        'enqueued_sequence_number': msg_snake.enqueued_sequence_number,
        'enqueued_time_utc': (msg_snake.enqueued_time_utc.isoformat() if
                              msg_snake.enqueued_time_utc else None),
        'expires_at_utc': (msg_snake.expires_at_utc.isoformat() if
                           msg_snake.expires_at_utc else None),
        'locked_until': (msg_snake.locked_until.isoformat() if
                         msg_snake.locked_until else None),
        'lock_token': msg_snake.lock_token,
        'sequence_number': msg_snake.sequence_number,
        'state': msg_snake.state,
        'subject': msg_snake.subject,
        'transaction_partition_key': msg_snake.transaction_partition_key
    })

    return result
