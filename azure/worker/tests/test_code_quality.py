import os.path
import subprocess
import sys
import unittest


ROOT_PATH = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.dirname(__file__))))


class TestCodeQuality(unittest.TestCase):
    def test_mypy(self):
        try:
            import mypy  # NoQA
        except ImportError:
            raise unittest.SkipTest('mypy module is missing')

        try:
            subprocess.run(
                [sys.executable, '-m', 'mypy', '-m', 'azure.worker'],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=ROOT_PATH)
        except subprocess.CalledProcessError as ex:
            output = ex.output.decode()
            raise AssertionError(
                f'mypy validation failed:\n{output}') from None
