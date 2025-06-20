# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from tests.utils import testutils


class TestFunctionInBluePrintOnly(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
            'functions_in_blueprint_only'

    def test_function_in_blueprint_only(self):
        r = self.webhost.request('GET', 'default_template')
        self.assertTrue(r.ok)


class TestFunctionsInBothBlueprintAndFuncApp(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
            'functions_in_both_blueprint_functionapp'

    def test_functions_in_both_blueprint_functionapp(self):
        r = self.webhost.request('GET', 'default_template')
        self.assertTrue(r.ok)

        r = self.webhost.request('GET', 'return_http')
        self.assertTrue(r.ok)


class TestMultipleFunctionRegisters(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
            'multiple_function_registers'

    def test_function_in_blueprint_only(self):
        r = self.webhost.request('GET', 'return_http')
        self.assertEqual(r.status_code, 404)


class TestOnlyBlueprint(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
            'only_blueprint'

    def test_only_blueprint(self):
        """Test if the default template of Http trigger in Python
        Function app
        will return OK
        """
        r = self.webhost.request('GET', 'default_template')
        self.assertEqual(r.status_code, 404)


class TestBlueprintDifferentDirectory(testutils.WebHostTestCase):
    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'blueprint_functions' / \
            'blueprint_different_dir'

    def test_blueprint_in_different_dir(self):
        r = self.webhost.request('GET', 'default_template')
        self.assertTrue(r.ok)

        r = self.webhost.request('GET', 'http_func')
        self.assertTrue(r.ok)
