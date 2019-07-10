import logging
import time

import azure.functions


logger = logging.getLogger('my function')


def main(req: azure.functions.HttpRequest):
    try:
        1 / 0
    except ZeroDivisionError:
        logger.error('a gracefully handled error', exc_info=True)
    time.sleep(0.05)
    return 'OK-sync'
