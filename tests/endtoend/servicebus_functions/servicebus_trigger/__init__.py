# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as azf


def main(msg: azf.ServiceBusMessage) -> str:
    result = json.dumps({
        'message_id': msg.message_id,
        'body': msg.get_body().decode('utf-8'),
        'content_type': msg.content_type,
        'delivery_count': msg.delivery_count,
        'expiration_time': (msg.expiration_time.isoformat() if
                            msg.expiration_time else None),
        'label': msg.label,
        'partition_key': msg.partition_key,
        'reply_to': msg.reply_to,
        'reply_to_session_id': msg.reply_to_session_id,
        'scheduled_enqueue_time': (msg.scheduled_enqueue_time.isoformat() if
                                   msg.scheduled_enqueue_time else None),
        'session_id': msg.session_id,
        'time_to_live': msg.time_to_live,
        'to': msg.to,
        'user_properties': msg.user_properties,

        'application_properties': msg.application_properties,
        'correlation_id': msg.correlation_id,
        'dead_letter_error_description': msg.dead_letter_error_description,
        'dead_letter_reason': msg.dead_letter_reason,
        'dead_letter_source': msg.dead_letter_source,
        'enqueued_sequence_number': msg.enqueued_sequence_number,
        'enqueued_time_utc': msg.enqueued_time_utc,
        'expires_at_utc': msg.expires_at_utc,
        'locked_until': msg.locked_until,
        'lock_token': msg.lock_token,
        'sequence_number': msg.sequence_number,
        'state': msg.state,
        'subject': msg.subject,
        'transaction_partition_key': msg.transaction_partition_key
    })

    return result
