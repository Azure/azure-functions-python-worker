# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from tests.utils import testutils


class TestDurableFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        # webhook for durable tests
        cls.env_variables['WEBSITE_HOSTNAME'] = "http:"
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
