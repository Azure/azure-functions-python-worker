# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from unittest import skipIf

from azure_functions_worker.utils.common import is_envvar_true
from tests.utils import testutils
from tests.utils.constants import DEDICATED_DOCKER_TEST, CONSUMPTION_DOCKER_TEST


@skipIf(is_envvar_true(DEDICATED_DOCKER_TEST)
        or is_envvar_true(CONSUMPTION_DOCKER_TEST),
        "Table functions which are used in the bindings in these tests"
        " has a bug with the table extension 1.0.0. "
        "https://github.com/Azure/azure-sdk-for-net/issues/33902.")
class GenericFunctions(testutils.WebHostTestCase):
    """Test Generic Functions with implicit output enabled

    With implicit output enabled for generic types, these tests cover
    scenarios where a function has both explicit and implicit output
    set to true. We prioritize explicit output. These tests check
    that no matter the ordering, the return type is still correctly set.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'generic_functions'

    def test_return_processed_last(self):
        # Tests the case where implicit and explicit return are true
        # in the same function and $return is processed before
        # the generic binding is

        r = self.webhost.request('GET', 'return_processed_last')
        self.assertEqual(r.status_code, 200)

    def test_return_not_processed_last(self):
        # Tests the case where implicit and explicit return are true
        # in the same function and the generic binding is processed
        # before $return

        r = self.webhost.request('GET', 'return_not_processed_last')
        self.assertEqual(r.status_code, 200)
