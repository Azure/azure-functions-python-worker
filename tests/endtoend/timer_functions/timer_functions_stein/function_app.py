# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="mytimer")
@app.schedule(
    schedule="*/1 * * * * *",
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=False,
)
def mytimer(mytimer: func.TimerRequest) -> None:
    logging.info("This timer trigger function executed successfully")
