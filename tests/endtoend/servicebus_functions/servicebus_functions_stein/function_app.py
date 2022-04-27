import json

import azure.functions as func

app = func.FunctionApp()


@app.route(route="put_message")
@app.write_service_bus_queue(
    arg_name="msg",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
def put_message(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body().decode('utf-8'))
    return 'OK'


@app.route(route="get_servicebus_triggered")
@app.read_blob(arg_name="file",
               path="python-worker-tests/test-servicebus-triggered.txt",
               connection="AzureWebJobsStorage")
def get_servicebus_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')


@app.service_bus_queue_trigger(
    arg_name="msg",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
@app.write_blob(arg_name="$return",
                path="python-worker-tests/test-servicebus-triggered.txt",
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
    })

    return result
