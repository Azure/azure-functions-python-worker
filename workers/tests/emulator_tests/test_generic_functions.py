# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import typing

from tests.utils import testutils


RETURN_TYPE_LOGS = (
    "This timer trigger function executed successfully",
    "Return string",
    "Return bytes",
    "Return dict",
    "Return list",
    "Return int",
    "Return double",
    "Return bool",
)


class TestGenericFunctions(testutils.WebHostTestCase):
    """Test Generic Functions with implicit output enabled

    With implicit output enabled for generic types, these tests cover
    scenarios where a function has both explicit and implicit output
    set to true. We prioritize explicit output. These tests check
    that no matter the ordering, the return type is still correctly set.
    """

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'generic_functions'

    def test_return_processed_last(self):
        # Tests the case where implicit and explicit return are true
        # in the same function and $return is processed before
        # the generic binding is
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)

        r = self.webhost.request('GET', 'return_processed_last')
        self.assertEqual(r.status_code, 200)

    def test_return_not_processed_last(self):
        # Tests the case where implicit and explicit return are true
        # in the same function and the generic binding is processed
        # before $return
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)

        r = self.webhost.request('GET', 'return_not_processed_last')
        self.assertEqual(r.status_code, 200)

    def test_return_types(self):
        out_resp = self.webhost.request('POST', 'table_out_binding')
        self.assertEqual(out_resp.status_code, 200)
        # Checking that the function app is okay
        self.wait_for_host_logs(RETURN_TYPE_LOGS, timeout=30)
        # Checking webhost status.
        r = self.webhost.request('GET', '', no_prefix=True,
                                 timeout=5)
        self.assertTrue(r.ok)

    def check_log_return_types(self, host_out: typing.List[str]):
        # Checks that functions executed correctly
        for expected in RETURN_TYPE_LOGS:
            self.assertIn(expected, host_out)

        # Checks for failed executions (TypeErrors, etc.)
        errors_found = False
        for log in host_out:
            if "Exception" in log:
                errors_found = True
                break
        self.assertFalse(errors_found)


class TestGenericFunctionsStein(TestGenericFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'generic_functions' / \
            'generic_functions_stein'
