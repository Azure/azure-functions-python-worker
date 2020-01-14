import json
import time

from azure_functions_worker import testutils


class TestEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventhub_functions'

    # @unittest.skip("Seems to be very unstable on CI")
    @testutils.retryable_test(3, 5)
    def test_eventhub_trigger(self):
        data = str(round(time.time()))
        doc = {'id': data}
        r = self.webhost.request('POST', 'eventhub_output',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        # Allow trigger to fire.
        time.sleep(5)

        # Check that the trigger has fired.
        r = self.webhost.request('GET', 'get_eventhub_triggered')
        self.assertEqual(r.status_code, 200)
        response = r.json()

        self.assertEqual(response, doc)
