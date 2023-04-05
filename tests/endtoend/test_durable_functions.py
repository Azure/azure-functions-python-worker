# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from unittest import skipIf

from azure_functions_worker.utils.common import is_envvar_true
from tests.utils import testutils
from tests.utils.constants import DEDICATED_DOCKER_TEST, \
    CONSUMPTION_DOCKER_TEST


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Docker container cannot set webhook required "
        "for durable tests")
class TestDurableFunctions(testutils.WebHostTestCase):
    env_variables = {}

    @classmethod
    def setUpClass(cls):
        # webhook for durable tests
        cls.env_variables['WEBSITE_HOSTNAME'] = "http://*:8080"
        super().setUpClass()

    @classmethod
    def get_libraries_to_install(cls):
        return ['azure-functions-durable']

    @classmethod
    def get_environment_variables(cls):
        return cls.env_variables

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'durable_functions'

    def test_durable(self):
        r = self.webhost.request('GET',
                                 'orchestrators/DurableFunctionsOrchestrator')
        self.assertEqual(r.status_code, 202)
