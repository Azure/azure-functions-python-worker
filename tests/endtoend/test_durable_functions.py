# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import time
from unittest import skipIf

import requests

from azure_functions_worker.utils.common import is_envvar_true
from tests.utils import testutils
from tests.utils.constants import DEDICATED_DOCKER_TEST, CONSUMPTION_DOCKER_TEST


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Docker tests cannot retrieve port needed for a webhook")
class TestDurableFunctions(testutils.WebHostTestCase):
    @classmethod
    def get_durable_webhooks(cls):
        return {'WEBSITE_HOSTNAME': 'http:'}

    @classmethod
    def get_environment_variables(cls):
        return {'WEBSITE_HOSTNAME': 'http:'}

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
