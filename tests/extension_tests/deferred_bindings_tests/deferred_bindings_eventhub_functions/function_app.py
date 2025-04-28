# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import typing

import azure.functions as func
# import azurefunctions.extensions.bindings.eventhub as eh

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="put_eh_ed_trigger")
@app.event_hub_output(arg_name="event",
                      event_hub_name="python-worker-ci-eventhub-one",
                      connection="AzureWebJobsEventHubConnectionString")
@app.route(route="put_eh_ed_trigger")
def put_eh_ed_trigger(req: func.HttpRequest, event: func.Out[str]) -> str:
    event.set(req.get_body())
    return 'OK'

# @app.function_name(name="eh_ed_trigger")
# @app.event_hub_message_trigger(
#     arg_name="event",
#     event_hub_name="python-worker-ci-eventhub-one",
#     connection="AzureWebJobsEventHubConnectionString")
# @app.blob_output(arg_name="$return",
#                  path="python-worker-tests/test-eventhub-triggered.txt",
#                  connection="AzureWebJobsStorage")
# async def eh_ed_trigger(event: func.EventHubEvent) -> bytes:
#     event_dict: typing.Mapping[str, typing.Any] = {
#         'body': event.get_body().decode('utf-8'),
#         # Uncomment this when the EnqueuedTimeUtc is fixed in azure-functions
#         # 'enqueued_time': event.enqueued_time.isoformat(),
#         'partition_key': event.partition_key,
#         'sequence_number': event.sequence_number,
#         'offset': event.offset,
#         'metadata': event.metadata
#     }

#     return json.dumps(event_dict)

# Retrieve the event data from storage blob and return it as Http response
@app.function_name(name="get_eh_ed_triggered")
@app.route(route="get_eh_ed_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-eventhub-triggered.txt",
                connection="AzureWebJobsStorage")
async def get_eh_ed_triggered(req: func.HttpRequest,
                                 file: func.InputStream) -> str:
    return func.HttpResponse(body=file.read().decode('utf-8'),
                             status_code=200,
                             mimetype='application/json')