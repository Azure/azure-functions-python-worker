# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib
import unittest
from unittest import mock

from tests.utils import testutils


class TestWebHostReadiness(unittest.TestCase):
    def test_reports_host_process_exit(self):
        process = mock.Mock()
        process.poll.return_value = 17
        proxy = testutils._WebHostProxy(process, 'http://127.0.0.1:5000')

        self.assertFalse(proxy.wait_until_ready())
        self.assertEqual(
            proxy.readiness_failure,
            'host process exited with code 17 before becoming ready')

    @mock.patch('tests.utils.testutils.time.sleep')
    @mock.patch('tests.utils.testutils.time.time', side_effect=[0, 0, 2])
    @mock.patch('tests.utils.testutils.requests.get')
    def test_reports_missing_function_registration(
            self, request, _time, _sleep):
        status_response = mock.Mock(status_code=200)
        status_response.json.return_value = {'state': 'Running'}
        functions_response = mock.Mock(status_code=200)
        functions_response.json.return_value = []
        request.side_effect = [status_response, functions_response]
        process = mock.Mock()
        process.poll.return_value = None
        proxy = testutils._WebHostProxy(process, 'http://127.0.0.1:5000')

        self.assertFalse(proxy.wait_until_ready(timeout=1))
        self.assertEqual(
            proxy.readiness_failure,
            'host reported Running but registered no functions')

    @mock.patch('tests.utils.testutils._get_worker_path')
    @mock.patch('tests.utils.testutils._WebHostProxy')
    @mock.patch('tests.utils.testutils.popen_webhost')
    @mock.patch('tests.utils.testutils._find_open_port', return_value=5000)
    def test_start_webhost_closes_failed_process(
            self, _port, popen, proxy_type, worker_path):
        expected_worker_path = pathlib.Path('/test/worker')
        worker_path.return_value = expected_worker_path
        proxy = proxy_type.return_value
        proxy.wait_until_ready.return_value = False
        proxy.readiness_failure = 'host did not report Running'

        with self.assertRaisesRegex(
                RuntimeError, 'host did not report Running') as context:
            testutils.start_webhost(script_dir=pathlib.Path('endtoend/app'))

        proxy.close.assert_called_once_with()
        self.assertIn(str(expected_worker_path), str(context.exception))
        popen.assert_called_once()

    @mock.patch('tests.utils.testutils._WebHostProxy')
    @mock.patch('tests.utils.testutils.popen_webhost')
    @mock.patch('tests.utils.testutils._find_open_port', return_value=5000)
    def test_start_webhost_returns_ready_proxy(
            self, _port, _popen, proxy_type):
        proxy = proxy_type.return_value
        proxy.wait_until_ready.return_value = True

        result = testutils.start_webhost(
            script_dir=pathlib.Path('endtoend/app'))

        self.assertIs(result, proxy)
        proxy.close.assert_not_called()


class TestWebHostTestCaseCleanup(unittest.TestCase):
    def test_partial_startup_can_be_torn_down(self):
        class PartialStartupCase(testutils.WebHostTestCase):
            @classmethod
            def get_script_dir(cls):
                return pathlib.Path('endtoend/app')

        PartialStartupCase.webhost = None
        PartialStartupCase.host_stdout = None

        with mock.patch(
                'tests.utils.testutils._teardown_func_app') as teardown:
            PartialStartupCase.tearDownClass()

        teardown.assert_called_once()
