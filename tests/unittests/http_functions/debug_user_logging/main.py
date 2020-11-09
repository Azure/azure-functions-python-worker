# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions


logger = logging.getLogger('my function')


def main(req: azure.functions.HttpRequest):
    logging.critical('logging critical', exc_info=True)
    logger.info('logging info', exc_info=True)
    logger.warning('logging warning', exc_info=True)
    logger.debug('logging debug', exc_info=True)
    logger.error('logging error', exc_info=True)
    return 'OK-user-debug'
