# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging
import azure.functions as azf


logger = logging.getLogger(__name__)


def main(msg: azf.QueueMessage) -> None:
    logging.info('trigger on message: %s', msg.get_body().decode('utf-8'))
