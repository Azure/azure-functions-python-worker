# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib
import subprocess
import sys
import unittest


ROOT_PATH = pathlib.Path(__file__).parent.parent.parent


class TestCodeQuality(unittest.TestCase):
    def test_mypy(self):
        try:
            import mypy  # NoQA
        except ImportError:
            raise unittest.SkipTest('mypy module is missing')

        try:
            subprocess.run(
                [sys.executable, '-m', 'mypy', '-m', 'azure_functions_worker'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ROOT_PATH))
        except subprocess.CalledProcessError as ex:
            if (sys.version_info[1] == 7
                    and sys.version_info[2] == 3):
                raise unittest.SkipTest('Subprocess start failing for 3.7.3')
            output = ex.output.decode()
            raise AssertionError(
                f'mypy validation failed:\n{output}') from None

    def test_flake8(self):
        try:
            import flake8  # NoQA
        except ImportError:
            raise unittest.SkipTest('flake8 moudule is missing')

        config_path = ROOT_PATH / '.flake8'
        if not config_path.exists():
            raise unittest.SkipTest('could not locate the .flake8 file')

        try:
            subprocess.run(
                [sys.executable, '-m', 'flake8', '--config', str(config_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(ROOT_PATH))
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode()
            raise AssertionError(
                f'flake8 validation failed:\n{output}') from None
