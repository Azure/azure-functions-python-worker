# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import datetime
import logging

import azure.functions as func

app = func.FunctionsApp()


@app.schedule(schedule="*/5 * * * * *", arg_name="timer", run_on_startup=False,
              use_monitor=False)
@app.route(route="http_timer_trigger")
def http_timer_trigger(timer: func.TimerRequest):
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if timer.past_due:
        logging.info('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)
