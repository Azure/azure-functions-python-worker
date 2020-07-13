# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import json

import azure.functions as func
from azure.eventhub import EventHubProducerClient, EventData


# An HttpTrigger to generating EventHub event from azure-eventhub SDK.
# Events generated from azure-eventhub contain the full metadata.
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

    return f'OK'
