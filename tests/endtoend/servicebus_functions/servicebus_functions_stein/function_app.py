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
