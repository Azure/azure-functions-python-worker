# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions as func


sdk_submodule_logger = logging.getLogger('azure.functions.submodule')


def main(req: func.HttpRequest):
    sdk_submodule_logger.info('sdk_submodule_logger info')
    sdk_submodule_logger.warning('sdk_submodule_logger warning')
    sdk_submodule_logger.debug('sdk_submodule_logger debug')
    sdk_submodule_logger.error('sdk_submodule_logger error', exc_info=True)
    return 'OK-sdk-submodule-logging'
