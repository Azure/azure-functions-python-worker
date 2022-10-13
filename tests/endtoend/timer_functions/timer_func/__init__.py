# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from datetime import datetime
import logging

import azure.functions as func


def main(mytimer: func.TimerRequest) -> None:
    with open("timer_log.txt", "a") as timer_trigger_log:
        timer_trigger_log.write(datetime.now().strftime("%H:%M:%S") + "\n")

    logging.info("This timer trigger function executed successfully")
