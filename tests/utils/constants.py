# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
UNIT_TESTS_FOLDER = TESTS_ROOT / pathlib.Path('unittests')
