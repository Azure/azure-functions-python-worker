# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import traceback

# Logging Prefixes
SDK_LOG_PREFIX = "azure_functions_runtime"

logger: logging.Logger = logging.getLogger(SDK_LOG_PREFIX)


def format_exception(exception: Exception) -> str:
    msg = str(exception) + "\n"
    msg += ''.join(traceback.format_exception(exception))
    return msg
