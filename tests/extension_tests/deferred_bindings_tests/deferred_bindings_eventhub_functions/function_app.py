# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func
import azurefunctions.extensions.bindings.eventhub as eh

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="put_bc_trigger")
@app.blob_output(arg_name="file",
                 path="python-worker-tests/test-blobclient-trigger.txt",
                 connection="AzureWebJobsStorage")
@app.route(route="put_bc_trigger")
def put_bc_trigger(req: func.HttpRequest, file: func.Out[str]) -> str:
    file.set(req.get_body())
    return 'OK'

# An HttpTrigger to generating EventHub event from EventHub Output Binding
# @app.function_name(name="eventhub_output")
# @app.route(route="eventhub_output")
# @app.event_hub_output(arg_name="event",
#                       event_hub_name="python-worker-ci-eventhub-one",
#                       connection="AzureWebJobsEventHubConnectionString")
# def eventhub_output(req: func.HttpRequest, event: func.Out[str]) -> str:
#     event.set(req.get_body().decode('utf-8'))
#     return 'OK'

# # This is an actual EventHub trigger which will convert the event data
# # into a storage blob.
# @app.function_name(name="eventhub_trigger")
# @app.event_hub_message_trigger(arg_name="event",
#                                event_hub_name="python-worker-ci-eventhub-one",
#                                connection="AzureWebJobsEventHubConnectionString"
#                                )
# @app.blob_output(arg_name="$return",
#                  path="python-worker-tests/test-eventhub-triggered.txt",
#                  connection="AzureWebJobsStorage")
# def eventhub_trigger(event: eh.EventData) -> bytes:
#     return bytes(event.body_as_str())

# # Retrieve the event data from storage blob and return it as Http response
# @app.function_name(name="get_eventhub_triggered")
# @app.route(route="get_eventhub_triggered")
# @app.blob_input(arg_name="file",
#                 path="python-worker-tests/test-eventhub-triggered.txt",
#                 connection="AzureWebJobsStorage")
# def get_eventhub_triggered(req: func.HttpRequest,
#                            file: func.InputStream) -> str:
#     return file.read().decode('utf-8')

# @app.event_hub_message_trigger(
#     arg_name="event",
#     event_hub_name="python-worker-ci-eventhub-one",
#     connection="AzureWebJobsEventHubConnectionString"
# )
# def eventhub_trigger(event: eh.EventHubData) -> str:
#     return event.body_as_str()