# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions

logger = logging.getLogger("my function")


def main(req: azure.functions.HttpRequest, context: azure.functions.Context):
    logger.info(f"Current retry count: {context.retry_context.retry_count}")
    logger.info(f"Max retry count: {context.retry_context.max_retry_count}")

    raise Exception("Testing retries")
