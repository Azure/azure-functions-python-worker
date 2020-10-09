# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import time

import azure.functions


logger = logging.getLogger('my function')


def main(req: azure.functions.HttpRequest):
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('a gracefully handled error', exc_info=True)
        logger.error('a gracefully handled critical error', exc_info=True)
    time.sleep(0.05)
    return 'OK-sync'
