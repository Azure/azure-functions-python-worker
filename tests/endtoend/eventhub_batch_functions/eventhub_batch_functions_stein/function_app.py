# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
import typing
import azure.functions as func
from azure.eventhub import EventHubProducerClient, EventData

app = func.FunctionApp()


# This is an actual EventHub trigger which handles Eventhub events in batches.
# It serializes multiple event data into a json and store it into a blob.
@app.function_name(name="eventhub_multiple")
@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="python-worker-ci-eventhub-batch",
    connection="AzureWebJobsEventHubConnectionString",
    data_type="string",
    cardinality="many")
@app.write_table(arg_name="$return",
                 connection="AzureWebJobsStorage",
                 table_name="EventHubBatchTest")
def eventhub_multiple(events):
    table_entries = []
    for event in events:
        json_entry = event.get_body()
        table_entry = json.loads(json_entry)
        table_entries.append(table_entry)

    table_json = json.dumps(table_entries)

    return table_json


# An HttpTrigger to generating EventHub event from EventHub Output Binding
@app.function_name(name="eventhub_output_batch")
@app.write_event_hub_message(arg_name="$return",
                             connection="AzureWebJobsEventHubConnectionString",
                             event_hub_name="python-worker-ci-eventhub-batch")
@app.route(route="eventhub_output_batch", binding_arg_name="out")
def eventhub_output_batch(req: func.HttpRequest, out: func.Out[str]) -> str:
    events = req.get_body().decode('utf-8')
    out.set('hello')
    return events


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_eventhub_batch_triggered")
@app.route(route="get_eventhub_batch_triggered/{id}")
@app.read_table(arg_name="testEntities",
                connection="AzureWebJobsStorage",
                table_name="EventHubBatchTest",
                partition_key="{id}")
def get_eventhub_batch_triggered(req: func.HttpRequest, testEntities):
    return func.HttpResponse(status_code=200, body=testEntities)


# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_metadata_batch_triggered")
@app.route(route="get_metadata_batch_triggered")
@app.read_blob(arg_name="file",
               path="python-worker-tests/test-metadata-batch-triggered.txt",
               connection="AzureWebJobsStorage")
def get_metadata_batch_triggered(req: func.HttpRequest,
                                 file: func.InputStream) -> str:
    return func.HttpResponse(body=file.read().decode('utf-8'),
                             status_code=200,
                             mimetype='application/json')


# This is an actual EventHub trigger which handles Eventhub events in batches.
# It serializes multiple event data into a json and store it into a blob.
@app.function_name(name="metadata_multiple")
@app.event_hub_message_trigger(
    arg_name="events",
    event_hub_name="python-worker-ci-eventhub-batch-metadata",
    connection="AzureWebJobsEventHubConnectionString",
    data_type="binary",
    cardinality="many")
@app.write_blob(arg_name="$return",
                path="python-worker-tests/test-metadata-batch-triggered.txt",
                connection="AzureWebJobsStorage")
def metadata_multiple(events: typing.List[func.EventHubEvent]) -> bytes:
    event_list = []
    for event in events:
        event_dict: typing.Mapping[str, typing.Any] = {
            'body': event.get_body().decode('utf-8'),
            'enqueued_time': event.enqueued_time.isoformat(),
            'partition_key': event.partition_key,
            'sequence_number': event.sequence_number,
            'offset': event.offset,
            'metadata': event.metadata
        }
        event_list.append(event_dict)

    return json.dumps(event_list)


# An HttpTrigger to generating EventHub event from azure-eventhub SDK.
# Events generated from azure-eventhub contain the full metadata.
@app.function_name(name="metadata_output_batch")
@app.route(route="metadata_output_batch")
def main(req: func.HttpRequest):
    # Get event count from http request query parameter
    count = int(req.params.get('count', '1'))

    # Parse event metadata from http request
    json_string = req.get_body().decode('utf-8')
    event_dict = json.loads(json_string)

    # Create an EventHub Client and event batch
    client = EventHubProducerClient.from_connection_string(
        os.getenv('AzureWebJobsEventHubConnectionString'),
        eventhub_name='python-worker-ci-eventhub-batch-metadata')

    # Generate new event based on http request with full metadata
    event_data_batch = client.create_batch()
    random_number = int(event_dict.get('body', '0'))
    for i in range(count):
        event_data_batch.add(EventData(str(random_number + i)))

    # Send out event into event hub
    with client:
        client.send_batch(event_data_batch)

    return 'OK'
