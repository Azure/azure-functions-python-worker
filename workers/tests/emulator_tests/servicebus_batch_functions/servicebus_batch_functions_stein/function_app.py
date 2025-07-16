import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="servicebus_output_batch")
@app.service_bus_queue_output(
    arg_name="msg",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue")
def servicebus_output_batch(req: func.HttpRequest, msg: func.Out[str]):
    msg.set(req.get_body().decode('utf-8'))
    return 'OK'


@app.route(route="get_servicebus_batch_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-servicebus-batch-triggered.txt",
                connection="AzureWebJobsStorage")
def get_servicebus_batch_triggered(req: func.HttpRequest,
                             file: func.InputStream) -> str:
    return func.HttpResponse(
        file.read().decode('utf-8'), mimetype='application/json')


@app.service_bus_queue_trigger(
    arg_name="events",
    connection="AzureWebJobsServiceBusConnectionString",
    queue_name="testqueue",
    cardinality="many")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-servicebus-batch-triggered.txt",
                 connection="AzureWebJobsStorage")
def servicebus_multiple(events) -> str:
    table_entries = []
    for event in events:
        json_entry = event.get_body().decode('utf-8')
        table_entry = json.loads(json_entry)
        table_entries.append(table_entry)
    table_json = json.dumps(table_entries)
    return table_json
