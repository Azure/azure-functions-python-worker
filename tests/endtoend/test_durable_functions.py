# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
import time
from unittest import skipIf

import requests
from tests.utils import testutils
from tests.utils.constants import CONSUMPTION_DOCKER_TEST, DEDICATED_DOCKER_TEST

from azure_functions_worker.utils.config_manager import is_envvar_true


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Docker tests cannot retrieve port needed for a webhook")
class TestDurableFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        os.environ["WEBSITE_HOSTNAME"] = "http:"
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        # Remove the WEBSITE_HOSTNAME environment variable
        os.environ.pop('WEBSITE_HOSTNAME')
        super().tearDownClass()

    @classmethod
    def get_environment_variables(cls):
        return cls.env_variables

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-functions-durable']

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'durable_functions'

    @testutils.retryable_test(3, 5)
    def test_durable(self):
        r = self.webhost.request('GET',
                                 'orchestrators/DurableFunctionsOrchestrator')
        time.sleep(4)  # wait for the activity to complete
        self.assertEqual(r.status_code, 202)
        content = json.loads(r.content)

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
