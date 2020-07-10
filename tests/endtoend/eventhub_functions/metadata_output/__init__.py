# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import json
from datetime import datetime

import azure.functions as func
from azure.eventhub import EventHubProducerClient, EventData


def main(req: func.HttpRequest):

    # Parse event metadata from http request
    json_string = req.get_body().decode('utf-8')
    event_dict = json.loads(json_string)

    # Create an EventHub Client and event batch
    client = EventHubProducerClient.from_connection_string(
        os.getenv('AzureWebJobsEventHubConnectionString'),
        eventhub_name='python-worker-ci-eventhub-one-metadata')

    # Generate new event based on http request with full metadata
    event_data_batch = client.create_batch()
    event_data_batch.add(EventData(event_dict.get('body')))

    # Send out event into event hub
    with client:
        client.send_batch(event_data_batch)

    return f'OK'
