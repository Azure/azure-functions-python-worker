# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from datetime import datetime
# flake8: noqa
import azure.functions as func
import time


def main(req: func.HttpRequest) -> func.HttpResponse:
    time.sleep(2)

    current_time = datetime.now().strftime("%H:%M:%S")
    return func.HttpResponse(f"{current_time}")
