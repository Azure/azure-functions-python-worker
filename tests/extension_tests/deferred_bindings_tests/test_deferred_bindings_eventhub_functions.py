# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import sys
import time
import unittest

from tests.utils import testutils


@unittest.skipIf(sys.version_info.minor <= 8, "The base extension"
                                              "is only supported for 3.9+.")
class TestDeferredBindingsEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.EXTENSION_TESTS_FOLDER / 'deferred_bindings_tests' / \
            'deferred_bindings_eventhub_functions'

    @classmethod
    def get_libraries_to_install(cls):
        return ['azurefunctions-extensions-bindings-eventhub']
    
    @testutils.retryable_test(3, 5)
    def test_ed_eventhub_trigger(self):
        # Generate a unique event body for EventHub eventme
        random_number = str(round(time.time()) % 1000)
        req_body = {
            'body': random_number
        }

        r = self.webhost.request('POST', 'put_eh_trigger',
                                 data=json.dumps(req_body))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Once the event get generated, allow function host to poll from
        # EventHub and wait for eventhub_trigger to execute,
        # converting the event metadata into a blob.
        time.sleep(5)

        # Call get_eh_ed_triggered to retrieve event metadata from blob.
        r = self.webhost.request('GET', 'get_eh_ed_triggered')

        # Waiting for the blob to get updated with the latest data from the
        # eventhub output binding
        time.sleep(5)
        self.assertEqual(r.status_code, 200)

        event = r.json()
        self.assertEqual(event['body'], random_number)