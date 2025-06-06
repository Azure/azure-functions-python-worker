import json
import jsonpickle

import azure.functions as func
import azurefunctions.extensions.bindings.servicebus as sb

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="put_message_sdk")
@app.service_bus_queue_output(
    arg_name="msg",
    connection="AzureWebJobsServiceBusSDKConnectionString",
    queue_name="testqueue")
def put_message_sdk(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body().decode('utf-8'))
    return 'OK'


@app.route(route="get_servicebus_triggered_sdk")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-servicebus-sdk-triggered.txt",
                connection="AzureWebJobsStorage")
def get_servicebus_triggered_sdk(req: func.HttpRequest,
                                 file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')


@app.service_bus_queue_trigger(
    arg_name="msg",
    connection="AzureWebJobsServiceBusSDKConnectionString",
    queue_name="testqueue")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-servicebus-sdk-triggered.txt",
                 connection="AzureWebJobsStorage")
def servicebus_trigger_sdk(msg: sb.ServiceBusReceivedMessage) -> str:
    msg_json = jsonpickle.encode(msg)
    body_json = jsonpickle.encode(msg.body)
    enqueued_time_json = jsonpickle.encode(msg.enqueued_time_utc)
    lock_token_json = jsonpickle.encode(msg.lock_token)
    result = json.dumps({
        'message': msg_json,
        'body': body_json,
        'enqueued_time_utc': enqueued_time_json,
        'lock_token': lock_token_json,
        'message_id': msg.message_id,
        'sequence_number': msg.sequence_number
    })

    return result
