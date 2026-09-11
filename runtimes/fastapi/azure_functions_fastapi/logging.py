# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging.handlers
import traceback

# Logging Prefixes
SDK_LOG_PREFIX = "azure.functions"

logger: logging.Logger = logging.getLogger(SDK_LOG_PREFIX)


def format_exception(exception: Exception) -> str:
    msg = str(exception) + "\n"
    msg += ''.join(traceback.format_exception(exception))
    return msg
