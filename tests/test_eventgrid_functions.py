import time
import requests
import uuid

from azure.functions_worker import testutils


class TestEventGridFunctions(testutils.WebHostTestCase):

    @classmethod
    def get_script_dir(cls):
        return 'eventgrid_functions'

    def request(self, meth, funcname, *args, **kwargs):
        request_method = getattr(requests, meth.lower())
        url = (f'{self.webhost._addr}/runtime/webhooks/'
               f'EventGridExtensionConfig')
        params = dict(kwargs.pop('params', {}))
        params['functionName'] = funcname
        if 'code' not in params:
            params['code'] = 'testSystemKey'
        headers = dict(kwargs.pop('headers', {}))
        headers['aeg-event-type'] = 'Notification'
        return request_method(url, *args, params=params, headers=headers,
                              **kwargs)

    def test_eventgrid_trigger(self):
        data = [{
            "topic": "test-topic",
            "subject": "test-subject",
            "eventType": "Microsoft.Storage.BlobCreated",
            "eventTime": "2018-01-01T00:00:00.000000Z",
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

        r = self.request('POST', 'eventgrid_trigger', json=data)
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

                self.assertEqual(
                    response,
                    {
                        'id': data[0]['id'],
                        'data': data[0]['data'],
                        'topic': data[0]['topic'],
                        'subject': data[0]['subject'],
                        'event_type': data[0]['eventType'],
                    }
                )
            except AssertionError as e:
                if try_no == max_retries - 1:
                    raise
            else:
                break
