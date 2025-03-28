# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import platform
import sys

from .constants import PYTHON_LANGUAGE_RUNTIME

from ..logging import logger
from ..version import VERSION


def change_cwd(new_cwd: str):
    if os.path.exists(new_cwd):
        os.chdir(new_cwd)
        logger.info('Changing current working directory to %s', new_cwd)
    else:
        logger.warning('Directory %s is not found when reloading', new_cwd)


def get_worker_metadata(protos):
    return protos.WorkerMetadata(
        runtime_name=PYTHON_LANGUAGE_RUNTIME,
        runtime_version=str(sys.version_info.major) + "." + str(sys.version_info.minor),
        worker_version=VERSION,
        worker_bitness=platform.machine(),
        custom_properties={})
