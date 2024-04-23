# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="return_processed_last")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="return_processed_last")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_processed_last(req: func.HttpRequest, testEntity):
    return func.HttpResponse(status_code=200)


@app.function_name(name="return_not_processed_last")
@app.generic_trigger(arg_name="req", type="httpTrigger",
                     route="return_not_processed_last")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="testEntities",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_not_processed_last(req: func.HttpRequest, testEntities):
    return func.HttpResponse(status_code=200)


@app.function_name(name="mytimer")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def mytimer(mytimer: func.TimerRequest, testEntity) -> None:
    logging.info("This timer trigger function executed successfully")


@app.function_name(name="return_string")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_string(mytimer: func.TimerRequest, testEntity):
    logging.info("Return string")
    return "hi!"


@app.function_name(name="return_bytes")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_bytes(mytimer: func.TimerRequest, testEntity):
    logging.info("Return bytes")
    return "test-dată"


@app.function_name(name="return_dict")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_dict(mytimer: func.TimerRequest, testEntity):
    logging.info("Return dict")
    return {"hello": "world"}


@app.function_name(name="return_list")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def return_list(mytimer: func.TimerRequest, testEntity):
    logging.info("Return list")
    return [1, 2, 3]
