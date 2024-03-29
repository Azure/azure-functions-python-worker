import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="put_message")
@app.generic_trigger(arg_name="req", type="httpTrigger", route="put_message")
@app.generic_output_binding(arg_name="msg",
                            type="serviceBus",
                            connection="AzureWebJobsServiceBusConnectionString",
                            queue_name="testqueue")
@app.generic_output_binding(arg_name="$return", type="http")
def put_message(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body().decode('utf-8'))
    return 'OK'


@app.function_name(name="get_servicebus_triggered")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="get_servicebus_triggered")
@app.generic_input_binding(arg_name="file",
                           type="blob",
                           path="python-worker-tests/test-servicebus-triggered.txt", # NoQA
                           connection="AzureWebJobsStorage")
@app.generic_output_binding(arg_name="$return", type="http")
def get_servicebus_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')


@app.generic_trigger(
    arg_name="msg",
    type="serviceBusTrigger",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
@app.generic_output_binding(arg_name="$return",
                            path="python-worker-tests/test-servicebus-triggered.txt", # NoQA
                            type="blob",
                            connection="AzureWebJobsStorage")
def servicebus_trigger(msg: func.ServiceBusMessage) -> str:
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
        'enqueued_time_utc': (msg.enqueued_time_utc.isoformat() if
                              msg.enqueued_time_utc else None),
        'expires_at_utc': (msg.expires_at_utc.isoformat() if
                           msg.expires_at_utc else None),
        'locked_until': (msg.locked_until.isoformat() if
                         msg.locked_until else None),
        'lock_token': msg.lock_token,
        'sequence_number': msg.sequence_number,
        'state': msg.state,
        'subject': msg.subject,
        'transaction_partition_key': msg.transaction_partition_key
    })

    return result
