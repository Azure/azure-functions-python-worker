import logging

import azure.functions
import does_not_exist  # Noqa


logger = logging.getLogger('my function')


def main(req: azure.functions.HttpRequest):
    logger.info('Function should fail before hitting main')
    return 'OK-async'
