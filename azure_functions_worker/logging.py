# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging.handlers
import sys
import traceback

# Logging Prefixes
SDK_LOG_PREFIX = "azure.functions"

logger: logging.Logger = logging.getLogger(SDK_LOG_PREFIX)


def format_exception(exception: Exception) -> str:
    msg = str(exception) + "\n"
    if (sys.version_info.major, sys.version_info.minor) < (3, 10):
        msg += ''.join(traceback.format_exception(
            etype=type(exception),
            tb=exception.__traceback__,
            value=exception))
    elif (sys.version_info.major, sys.version_info.minor) >= (3, 10):
        msg += ''.join(traceback.format_exception(exception))
    else:
        msg = str(exception)
    return msg
