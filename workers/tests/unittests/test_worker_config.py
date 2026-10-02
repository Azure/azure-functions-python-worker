# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import pathlib
import unittest


WORKERS_ROOT = pathlib.Path(__file__).resolve().parents[2]
TEST_WORKER_CONFIG = WORKERS_ROOT / 'python' / 'test' / 'worker.config.json'


class TestWorkerConfig(unittest.TestCase):
    def test_test_worker_uses_portable_python_executable(self):
        config = json.loads(TEST_WORKER_CONFIG.read_text())
        description = config['description']

        self.assertEqual(description['defaultExecutablePath'], 'python')
        self.assertEqual(description['defaultWorkerPath'], 'worker.py')
