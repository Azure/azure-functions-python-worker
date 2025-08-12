# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib
import subprocess
import sys
import unittest

ROOT_PATH = pathlib.Path(__file__).parent.parent.parent.parent


class TestCodeQuality(unittest.TestCase):

    def test_flake8(self):
        try:
            import flake8  # NoQA
        except ImportError as e:
            raise unittest.SkipTest('flake8 module is missing') from e

        config_path = ROOT_PATH / '.flake8'
        if not config_path.exists():
            raise unittest.SkipTest('could not locate the .flake8 file')

        try:
            subprocess.run(
                [sys.executable, '-m', 'flake8', '--config', str(config_path),
                 'azure_functions_runtime_v1',],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ROOT_PATH))
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode()
            raise AssertionError(
                'flake8 validation failed:\n%s', output) from None
