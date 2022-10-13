# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
from datetime import datetime

import azure.functions as func

app = func.FunctionApp()


@app.function_name(name="mytimer")
@app.schedule(schedule="*/2 * * * * *", arg_name="mytimer",
              run_on_startup=True,
              use_monitor=False)
def mytimer(mytimer: func.TimerRequest) -> None:
    with open("../timer_log.txt", "a") as timer_trigger_log:
        timer_trigger_log.write(datetime.now().strftime("%H:%M:%S") + "\n")

    logging.info("This timer trigger function executed successfully")
