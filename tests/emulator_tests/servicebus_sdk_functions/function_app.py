import json

import azure.functions as func
import azurefunctions.extensions.bindings.servicebus as sb

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="put_message")
@app.service_bus_queue_output(
    arg_name="msg",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
def put_message(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body().decode('utf-8'))
    return 'OK'


@app.route(route="get_servicebus_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-servicebus-sdk-triggered.txt",
                connection="AzureWebJobsStorage")
def get_servicebus_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')


@app.service_bus_queue_trigger(
    arg_name="msg",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-servicebus-sdk-triggered.txt",
                 connection="AzureWebJobsStorage")
def servicebus_trigger(msg: sb.ServiceBusReceivedMessage) -> str:
    result = json.dumps({
        'message': msg,
        'body': msg.body,
        'enqueued_time_utc': msg.enqueued_time_utc,
        'lock_token': msg.lock_token,
        'locked_until': msg.locked_until,
        'message_id': msg.message_id,
        'sequence_number': msg.sequence_number
    })

    return result
