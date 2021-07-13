# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions as func


sdk_logger = logging.getLogger('azure.functions')


def main(req: func.HttpRequest):
    sdk_logger.info('sdk_logger info')
    sdk_logger.warning('sdk_logger warning')
    sdk_logger.debug('sdk_logger debug')
    sdk_logger.error('sdk_logger error', exc_info=True)
    return 'OK-sdk-logger'
