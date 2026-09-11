# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import platform
import sys

from .constants import PYTHON_LANGUAGE_RUNTIME
from ..version import VERSION

def get_worker_metadata(protos):
    return protos.WorkerMetadata(
        runtime_name=PYTHON_LANGUAGE_RUNTIME,
        runtime_version=str(sys.version_info.major) + "." + str(sys.version_info.minor),
        worker_version=VERSION,
        worker_bitness=platform.machine(),
        custom_properties={})