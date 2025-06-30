# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func


def main(mytimer: func.TimerRequest) -> None:
    logging.info("This timer trigger function executed successfully")
