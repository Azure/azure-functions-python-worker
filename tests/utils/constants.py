# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib

# PROJECT_ROOT refers to the path to azure-functions-python-worker
# TODO: Find root folder without .parent
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
WORKER_CONFIG = PROJECT_ROOT / '.testconfig'

# E2E Integration Flags and Configurations
PYAZURE_INTEGRATION_TEST = "PYAZURE_INTEGRATION_TEST"
PYAZURE_WORKER_DIR = "PYAZURE_WORKER_DIR"

# Debug Flags
PYAZURE_WEBHOST_DEBUG = "PYAZURE_WEBHOST_DEBUG"

# CI test constants
CONSUMPTION_DOCKER_TEST = "false"
DEDICATED_DOCKER_TEST = "false"
