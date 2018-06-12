import json
import time

from azure.functions_worker import testutils


class TestServiceBusFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'servicebus_functions'

    def test_servicebus_basic(self):
        data = str(round(time.time()))
        r = self.webhost.request('POST', 'put_message',
                                 data=data)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.text, 'OK')

        max_retries = 10

        for try_no in range(max_retries):
            # wait for trigger to process the queue item
            time.sleep(1)

            try:
                r = self.webhost.request('GET', 'get_servicebus_triggered')
                self.assertEqual(r.status_code, 200)
                msg = r.json()
                self.assertEqual(msg['body'], data)
            except (AssertionError, json.JSONDecodeError):
                if try_no == max_retries - 1:
                    raise
            else:
                break
