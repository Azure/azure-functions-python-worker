# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import json

import azure.functions as func
from azure.eventhub import EventData
from azure.eventhub.aio import EventHubProducerClient


# An HttpTrigger to generating EventHub event from azure-eventhub SDK.
# Events generated from azure-eventhub contain the full metadata.
async def main(req: func.HttpRequest):

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

    return f'OK'
