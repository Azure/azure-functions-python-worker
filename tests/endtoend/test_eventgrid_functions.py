# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import time
import unittest
import uuid

import requests

from azure_functions_worker import testutils


class TestEventGridFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return testutils.E2E_TESTS_FOLDER / 'eventgrid_functions'

    def eventgrid_webhook_request(self, meth, funcname, *args, **kwargs):
        request_method = getattr(requests, meth.lower())
        url = f'{self.webhost._addr}/runtime/webhooks/eventgrid'
        params = dict(kwargs.pop('params', {}))
        params['functionName'] = funcname
        if 'code' not in params:
            params['code'] = 'testSystemKey'
        headers = dict(kwargs.pop('headers', {}))
        headers['aeg-event-type'] = 'Notification'
        return request_method(url, *args, params=params, headers=headers,
                              **kwargs)

    @testutils.retryable_test(3, 5)
    @unittest.skip("Run locally. Running on Azure fails with 401/403 as the"
                   "host does not pick up the SecretKey from the"
                   "azure_functions_worker.testutils.py.SECRETS_TEMPLATE and"
                   "because of which we cannot test eventGrid webhook"
                   "invocation correctly.")
    def test_eventgrid_trigger(self):
        """test event_grid trigger

        This test calls the eventgrid_trigger function, sends in `data` as body
        to the webhook for eventgrid. Once the event is received, the function
        writes the data to the blob store.

        Then get_eventgrid_triggered gets called (httpTrigger) and takes blob
        input binding, reading the previously written text in blob store
        `python-worker-tests/test-eventgrid-triggered.txt`, and then we validate
        that the written text matches the one passed to the eventgrid trigger.
        """
        data = [{
            "topic": "test-topic",
            "subject": "test-subject",
            "eventType": "Microsoft.Storage.BlobCreated",
            "eventTime": "2018-01-01T00:00:00.000000123Z",
            "id": str(uuid.uuid4()),
            "data": {
                "api": "PutBlockList",
                "clientRequestId": "2c169f2f-7b3b-4d99-839b-c92a2d25801b",
                "requestId": "44d4f022-001e-003c-466b-940cba000000",
                "eTag": "0x8D562831044DDD0",
                "contentType": "application/octet-stream",
                "contentLength": 2248,
                "blobType": "BlockBlob",
                "ur1": "foo",
                "sequencer": "000000000000272D000000000003D60F",
                "storageDiagnostics": {
                    "batchId": "b4229b3a-4d50-4ff4-a9f2-039ccf26efe9"
                }
            },
            "dataVersion": "",
            "metadataVersion": "1"
        }]

        r = self.eventgrid_webhook_request('POST', 'eventgrid_trigger',
                                           json=data)
        self.assertEqual(r.status_code, 202)

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire.
            time.sleep(2)

            try:
                # Check that the trigger has fired.
                r = self.webhost.request('GET', 'get_eventgrid_triggered')
                self.assertEqual(r.status_code, 200)

                response = r.json()
                self.assertLessEqual(response.items(), data[0].items())
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break

    @testutils.retryable_test(1, 5)
    def test_eventgrid_output_binding(self):
        """test event_grid output binding

        This test needs three functions to work.
        1. `eventgrid_output_binding`
        2. `eventgrid_output_binding_message_to_blobstore`
        3. `eventgrid_output_binding_success`

        This test calls the eventgrid_output_binding function, sends in a unique
        uuid as `data` in the body to the httpTrigger which sends in that value
        in the eventGrid output data. The eventGrid topic is configured to
        send the event to a storage queue.

        The second function (`eventgrid_output_binding_message_to_blobstore`)
        reads from that storage queue and puts into a blob store.

        The third function (`eventgrid_output_binding_success`) reads the
        text from the blob store and compares with the expected result. The
        unique uuid should confirm if the message went through correctly to
        EventGrid and came back as a blob.
        """

        test_uuid = uuid.uuid4().__str__()
        expected_response = "Sent event with subject: {}, id: {}, data: {}, " \
                            "event_type: {} to EventGrid!".format(
                                "test-subject", "test-id",
                                f"{{'test_uuid': '{test_uuid}'}}",
                                "test-event-1")
        expected_final_data = {
            'id': 'test-id', 'subject': 'test-subject', 'dataVersion': '1.0',
            'eventType': 'test-event-1',
            'data': {'test_uuid': test_uuid}
        }

        r = self.webhost.request('GET', 'eventgrid_output_binding',
                                 params={'test_uuid': test_uuid})
        self.assertEqual(r.status_code, 200)
        response = r.text

        self.assertEqual(expected_response, response)

        max_retries = 10
        for try_no in range(max_retries):
            # Allow trigger to fire.
            time.sleep(2)

            try:
                # Check that the trigger has fired.
                r = self.webhost.request('GET',
                                         'eventgrid_output_binding_success')
                self.assertEqual(r.status_code, 200)
                response = r.json()

                # list of fields to check are limited as other fields contain
                # datetime or other uncertain values
                for f in ['data', 'id', 'eventType', 'subject', 'dataVersion']:
                    self.assertEqual(response[f], expected_final_data[f])

            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break
