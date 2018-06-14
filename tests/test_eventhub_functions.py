import json
import time

from azure.functions_worker import testutils


class TestEventHubFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'eventhub_functions'

    def test_eventhub_trigger(self):
        data = str(round(time.time()))
        doc = {'id': data}
        r = self.webhost.request('POST', 'eventhub_output',
                                 data=json.dumps(doc))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire.
            time.sleep(2)

            try:
                # Check that the trigger has fired.
                r = self.webhost.request('GET', 'get_eventhub_triggered')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                self.assertEqual(
                    response,
                    doc
                )
            except AssertionError as e:
                if try_no == max_retries - 1:
                    raise
            else:
                break
