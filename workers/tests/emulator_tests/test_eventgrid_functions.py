# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import os
import queue
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from tests.utils import testutils


_EVENT_GRID_TOPIC_KEY = 'local-event-grid-key'


def _create_eventgrid_request_handler(captured_requests):
    """Create the local receiver for Event Grid output binding requests.

    The handler records each request's path, query, headers, and JSON body in
    a queue for test assertions, then returns a successful response.
    """

    class EventGridRequestHandler(BaseHTTPRequestHandler):

        def do_POST(self):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            request_url = urlparse(self.path)
            captured_requests.put({
                'path': request_url.path,
                'query': parse_qs(request_url.query),
                'headers': {key.lower(): value
                            for key, value in self.headers.items()},
                'body': json.loads(body),
            })

            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()

        def log_message(self, message_format, *args):
            pass

    return EventGridRequestHandler


class TestEventGridFunctions(testutils.WebHostTestCase):

    @classmethod
    def setUpClass(cls):
        cls.eventgrid_requests = queue.Queue()
        request_handler = _create_eventgrid_request_handler(
            cls.eventgrid_requests)
        cls.eventgrid_server = ThreadingHTTPServer(
            (testutils.LOCALHOST, 0), request_handler)
        cls.eventgrid_server.daemon_threads = True
        cls.eventgrid_thread = threading.Thread(
            target=cls.eventgrid_server.serve_forever,
            daemon=True)

        server_port = cls.eventgrid_server.server_address[1]
        os.environ['AzureWebJobsEventGridTopicUri'] = (
            f'http://{testutils.LOCALHOST}:{server_port}/api/events')
        os.environ['AzureWebJobsEventGridConnectionKey'] = \
            _EVENT_GRID_TOPIC_KEY
        cls.eventgrid_thread.start()

        try:
            super().setUpClass()
        except Exception:
            cls._stop_eventgrid_server()
            raise

    @classmethod
    def tearDownClass(cls):
        try:
            if getattr(cls, 'webhost', None) is not None:
                super().tearDownClass()
        finally:
            cls._stop_eventgrid_server()

    @classmethod
    def _stop_eventgrid_server(cls):
        server = getattr(cls, 'eventgrid_server', None)
        if server is not None:
            server.shutdown()
            server.server_close()
            cls.eventgrid_server = None

        server_thread = getattr(cls, 'eventgrid_thread', None)
        if server_thread is not None:
            server_thread.join(timeout=5)
            cls.eventgrid_thread = None

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventgrid_functions'

    def eventgrid_webhook_request(self, meth, funcname, *args, **kwargs):
        """Send an Event Grid notification to the local Functions host.

        The request targets the Event Grid system webhook with the function
        name, test master key, and notification headers required by the host.
        """

        request_method = getattr(requests, meth.lower())
        url = f'{self.webhost._addr}/runtime/webhooks/eventgrid'
        params = dict(kwargs.pop('params', {}))
        params['functionName'] = funcname
        if 'code' not in params:
            params['code'] = 'testMasterKey'
        headers = dict(kwargs.pop('headers', {}))
        headers['aeg-event-type'] = 'Notification'
        headers.setdefault('Content-Type', 'application/json')
        return request_method(url, *args, params=params, headers=headers,
                              **kwargs)

    def test_eventgrid_trigger(self):
        """Verify the local host processes an Event Grid trigger.

        The test posts an event to the Event Grid webhook, then polls an HTTP
        function that reads the triggered function's blob output from Azurite.
        It verifies the stored event matches the event that was posted.
        """

        event = {
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
        }

        response = self.eventgrid_webhook_request(
            'POST', 'eventgrid_trigger', json=[event])
        self.assertEqual(response.status_code, 202)

        max_retries = 10

        for try_no in range(max_retries):
            # Allow trigger to fire.
            time.sleep(2)

            try:
                response = self.webhost.request(
                    'GET', 'get_eventgrid_triggered')
                self.assertEqual(response.status_code, 200)

                response_data = response.json()
                self.assertEqual(response_data['id'], event['id'])
                self.assertEqual(response_data['data'], event['data'])
                self.assertEqual(response_data['topic'], event['topic'])
                self.assertEqual(response_data['subject'], event['subject'])
                self.assertEqual(
                    response_data['event_type'], event['eventType'])
            except AssertionError:
                if try_no == max_retries - 1:
                    raise
            else:
                break

    def test_eventgrid_output_binding(self):
        """Verify an Event Grid output binding publishes the expected event.

        The test invokes an HTTP function that emits an Event Grid event, then
        reads the resulting POST from the local receiver and validates its
        endpoint, content type, and event payload.
        """

        while not self.eventgrid_requests.empty():
            self.eventgrid_requests.get_nowait()

        test_uuid = str(uuid.uuid4())
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

        response = self.webhost.request(
            'GET', 'eventgrid_output_binding',
            params={'test_uuid': test_uuid})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, expected_response)

        try:
            captured_request = self.eventgrid_requests.get(timeout=5)
        except queue.Empty:
            self.fail('Event Grid output binding did not publish an event')

        self.assertEqual(captured_request['path'], '/api/events')
        self.assertIn('api-version', captured_request['query'])
        self.assertEqual(
            captured_request['headers']['content-type'].split(';')[0],
            'application/json')

        published_events = captured_request['body']
        self.assertEqual(len(published_events), 1)
        published_event = published_events[0]
        for field, expected_value in expected_final_data.items():
            self.assertEqual(published_event[field], expected_value)


class TestEventGridFunctionsStein(TestEventGridFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventgrid_functions' / \
            'eventgrid_functions_stein'


class TestEventGridFunctionsGeneric(TestEventGridFunctions):

    @classmethod
    def get_script_dir(cls):
        return testutils.EMULATOR_TESTS_FOLDER / 'eventgrid_functions' / \
            'eventgrid_functions_stein' / 'generic'
