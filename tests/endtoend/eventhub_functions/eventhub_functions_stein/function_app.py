import json
import os
import typing

from azure.eventhub import EventData
from azure.eventhub.aio import EventHubProducerClient

import azure.functions as func

app = func.FunctionApp()


# An HttpTrigger to generating EventHub event from EventHub Output Binding
@app.function_name(name="eventhub_output")
@app.route(route="eventhub_output")
@app.write_event_hub_message(arg_name="event",
                             event_hub_name="python-worker-ci-eventhub-one",
                             connection="AzureWebJobsEventHubConnectionString")
def eventhub_output(req: func.HttpRequest, event: func.Out[str]):
    event.set(req.get_body().decode('utf-8'))
    return 'OK'


# This is an actual EventHub trigger which will convert the event data
# into a storage blob.
@app.function_name(name="eventhub_trigger")
@app.event_hub_message_trigger(arg_name="event",
                               event_hub_name="python-worker-ci-eventhub-one",
                               connection="AzureWebJobsEventHubConnectionString"
                               )
@app.write_blob(arg_name="$return",
                path="python-worker-tests/test-eventhub-triggered.txt",
                connection="AzureWebJobsStorage")
def eventhub_trigger(event: func.EventHubEvent) -> bytes:
    return event.get_body()


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_eventhub_triggered")
@app.route(route="get_eventhub_triggered")
@app.read_blob(arg_name="file",
               path="python-worker-tests/test-eventhub-triggered.txt",
               connection="AzureWebJobsStorage")
def get_eventhub_triggered(req: func.HttpRequest,
                           file: func.InputStream) -> str:
    return file.read().decode('utf-8')


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_metadata_triggered")
@app.route(route="get_metadata_triggered")
@app.read_blob(arg_name="file",
               path="python-worker-tests/test-metadata-triggered.txt",
               connection="AzureWebJobsStorage")
async def get_metadata_triggered(req: func.HttpRequest,
                                 file: func.InputStream) -> str:
    return func.HttpResponse(body=file.read().decode('utf-8'),
                             status_code=200,
                             mimetype='application/json')


# An HttpTrigger to generating EventHub event from azure-eventhub SDK.
# Events generated from azure-eventhub contain the full metadata.
@app.function_name(name="metadata_output")
@app.route(route="metadata_output")
async def metadata_output(req: func.HttpRequest):
    # Parse event metadata from http request
    json_string = req.get_body().decode('utf-8')
    event_dict = json.loads(json_string)

    # Create an EventHub Client and event batch
    client = EventHubProducerClient.from_connection_string(
        os.getenv('AzureWebJobsEventHubConnectionString'),
        eventhub_name='python-worker-ci-eventhub-one-metadata')

    # Generate new event based on http request with full metadata
    event_data_batch = await client.create_batch()
    event_data_batch.add(EventData(event_dict.get('body')))

    # Send out event into event hub
    try:
        await client.send_batch(event_data_batch)
    finally:
        await client.close()

    return 'OK'


@app.function_name(name="metadata_trigger")
@app.event_hub_message_trigger(
    arg_name="event",
    event_hub_name="python-worker-ci-eventhub-one-metadata",
    connection="AzureWebJobsEventHubConnectionString")
@app.write_blob(arg_name="$return",
                path="python-worker-tests/test-metadata-triggered.txt",
                connection="AzureWebJobsStorage")
async def metadata_trigger(event: func.EventHubEvent) -> bytes:
    event_dict: typing.Mapping[str, typing.Any] = {
        'body': event.get_body().decode('utf-8'),
        # Uncomment this when the EnqueuedTimeUtc is fixed in azure-functions
        # 'enqueued_time': event.enqueued_time.isoformat(),
        'partition_key': event.partition_key,
        'sequence_number': event.sequence_number,
        'offset': event.offset,
        'metadata': event.metadata
    }

    return json.dumps(event_dict)
