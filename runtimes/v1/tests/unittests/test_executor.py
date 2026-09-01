import concurrent.futures
import threading
import unittest
from unittest.mock import MagicMock

from azure_functions_runtime_v1.utils.executor import (
    invocation_id_cv,
    run_sync_func,
)


class TestSyncInvocationContext(unittest.TestCase):

    def setUp(self):
        self.context = MagicMock()
        self.context.thread_local_storage = threading.local()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def tearDown(self):
        self.executor.shutdown()

    def _get_current_invocation_ids(self):
        return (self.context.thread_local_storage.invocation_id,
                invocation_id_cv.get())

    def test_invocation_id_cleared_after_success(self):
        observed_invocation_ids = []

        def invoke():
            observed_invocation_ids.append(self._get_current_invocation_ids())

        self.executor.submit(
            run_sync_func,
            'test-invocation', self.context, invoke, {}).result()

        remaining_invocation_ids = self.executor.submit(
            self._get_current_invocation_ids).result()
        self.assertEqual(
            observed_invocation_ids,
            [('test-invocation', 'test-invocation')])
        self.assertEqual(remaining_invocation_ids, (None, None))

    def test_invocation_id_cleared_after_exception(self):
        def invoke():
            self.assertEqual(
                self._get_current_invocation_ids(),
                ('test-invocation', 'test-invocation'))
            raise RuntimeError('test error')

        with self.assertRaisesRegex(RuntimeError, 'test error'):
            self.executor.submit(
                run_sync_func,
                'test-invocation', self.context, invoke, {}).result()

        remaining_invocation_ids = self.executor.submit(
            self._get_current_invocation_ids).result()
        self.assertEqual(remaining_invocation_ids, (None, None))
