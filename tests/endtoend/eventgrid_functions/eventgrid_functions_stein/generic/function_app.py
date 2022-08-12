import json
from datetime import datetime
import azure.functions as func

from azure_functions_worker import logging

app = func.FunctionApp()


@app.function_name(name="eventGridTrigger")
@app.event_grid_trigger(arg_name="event", type="eventGridTrigger")
@app.generic_output_binding(
    arg_name="$return",
    type="blob",
    connection="AzureWebJobsStorage",
    path="python-worker-tests/test-eventgrid-triggered.txt")
def event_grid_trigger(event: func.EventGridEvent) -> str:
    logging.info("Event grid function is triggered!")
    return json.dumps({
        'id': event.id,
        'data': event.get_json(),
        'topic': event.topic,
        'subject': event.subject,
        'event_type': event.event_type,
    })


@app.function_name(name="eventgrid_output_binding")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="eventgrid_output_binding")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_output_binding(
    arg_name="outputEvent",
    type="eventGrid",
    topic_endpoint_uri="AzureWebJobsEventGridTopicUri",
    topic_key_setting="AzureWebJobsEventGridConnectionKey")
def eventgrid_output_binding(
        req: func.HttpRequest,
        outputEvent: func.Out[func.EventGridOutputEvent]) -> func.HttpResponse:
    test_uuid = req.params.get('test_uuid')
    data_to_event_grid = func.EventGridOutputEvent(id="test-id",
                                                   data={
                                                       "test_uuid": test_uuid
                                                   },
                                                   subject="test-subject",
                                                   event_type="test-event-1",
                                                   event_time=datetime.utcnow(),
                                                   data_version="1.0")

    outputEvent.set(data_to_event_grid)
    r_value = "Sent event with subject: {}, id: {}, data: {}, event_type: {} " \
              "to EventGrid!".format(data_to_event_grid.subject,
                                     data_to_event_grid.id,
                                     data_to_event_grid.get_json(),
                                     data_to_event_grid.event_type)
    return func.HttpResponse(r_value)


@app.function_name(name="eventgrid_output_binding_message_to_blobstore")
@app.generic_trigger(arg_name="msg",
                     type="queueTrigger",
                     queue_name="test-event-grid-storage-queue",
                     connection="AzureWebJobsStorage")
@app.generic_output_binding(
    arg_name="$return",
    type="blob",
    connection="AzureWebJobsStorage",
    path="python-worker-tests/test-eventgrid-output-binding.txt")
def eventgrid_output_binding_message_to_blobstore(
        msg: func.QueueMessage) -> bytes:
    return msg.get_body()


@app.function_name(name="eventgrid_output_binding_success")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="eventgrid_output_binding_success")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="file",
    type="blob",
    path="python-worker-tests/test-eventgrid-output-binding.txt",
    connection="AzureWebJobsStorage")
def eventgrid_output_binding_success(
        req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.function_name(name="get_eventgrid_triggered")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="get_eventgrid_triggered")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="file",
    type="blob",
    path="python-worker-tests/test-eventgrid-triggered.txt",
    connection="AzureWebJobsStorage")
def get_eventgrid_triggered(
        req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')
