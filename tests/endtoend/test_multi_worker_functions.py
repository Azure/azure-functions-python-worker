# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
from threading import Thread
from unittest.mock import patch

from tests.utils import testutils


class TestWorkerProcessCountStein(testutils.WebHostTestCase):
    """Test the Http Trigger with setting up the python worker process count to 2.
     This tests will check if worker1 indexes the function in metadata request
     and worker2 indexes the function in the load request since worker2 does not
     call metadata request.
    """
    @classmethod
    def setUpClass(cls):
        os_environ = os.environ.copy()
        os_environ['FUNCTIONS_WORKER_PROCESS_COUNT'] = '2'
        cls._patch_environ = patch.dict('os.environ', os_environ)
        cls._patch_environ.start()
        super().setUpClass()

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'http_functions' / \
            'http_functions_stein'

    def test_http_func_with_worker_process_count(self):
        """Test if the default template of Http trigger in Python Function app
            will return OK
            """
        def http_req():
            r = self.webhost.request('GET', 'default_template')
            self.assertTrue(r.ok)

        # creating 2 different threads to send HTTP request
        trd1 = Thread(target=http_req, args=(0,))
        trd2 = Thread(target=http_req, args=(1,))
        trd1.start()
        trd2.start()
        trd1.join()
        trd2.join()
