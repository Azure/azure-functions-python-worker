# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func


def main(mytimer: func.TimerRequest, testEntity):
    logging.info("Return bool")
    return True
