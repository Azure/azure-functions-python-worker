# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
from unittest.mock import patch

import requests
from tests.utils import testutils
import os


class TestDurableFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        # Webhook for durable functions
        os.environ['WEBSITE_HOSTNAME'] = f'http:'

        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def tearDownClass(self):
        super().tearDownClass()
        self._patch_environ.stop()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'durable_functions'

    def test_durable(self):
        r = self.webhost.request('GET',
                                 'orchestrators/DurableFunctionsOrchestrator')
        self.assertEqual(r.status_code, 202)
        content = json.loads(r.content)

        time.sleep(2)  # wait for the activity to complete
        status = requests.get(content['statusQueryGetUri'])
        self.assertEqual(status.status_code, 200)

        status_content = json.loads(status.content)
        self.assertEqual(status_content['runtimeStatus'], 'Completed')
        self.assertEqual(status_content['output'],
                         ['Hello Tokyo!', 'Hello Seattle!', 'Hello London!'])


class TestDurableFunctionsStein(TestDurableFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'durable_functions' / \
                                            'durable_functions_stein'
