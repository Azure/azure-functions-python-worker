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


@app.function_name(name="mytimer2")
@app.schedule(schedule="*/1 * * * * *", arg_name="mytimer",
              run_on_startup=False,
              use_monitor=False)
@app.generic_input_binding(
    arg_name="testEntity",
    type="table",
    connection="AzureWebJobsStorage",
    table_name="EventHubBatchTest")
def mytimer2(mytimer: func.TimerRequest, testEntity):
    logging.info("Timer trigger with none return and no type hint")
