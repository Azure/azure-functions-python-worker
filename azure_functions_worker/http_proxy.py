import threading

from .logging import logger


class HttpCoordinator:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HttpCoordinator, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._http_requests = {}
            self._http_responses = {}
            self._http_requests_invoc_event = {}
            self._http_responses_invoc_event = {}
            self._initialized = True

    def get_request_event(self, invoc_id):
        if invoc_id not in self._http_requests_invoc_event:
            self._http_requests_invoc_event[invoc_id] = threading.Event()
        return self._http_requests_invoc_event[invoc_id]

    def get_response_event(self, invoc_id):
        if invoc_id not in self._http_responses_invoc_event:
            self._http_responses_invoc_event[invoc_id] = threading.Event()
        return self._http_responses_invoc_event[invoc_id]

    def add_http_invoc_request(self, invoc_id, http_request):
        logger.info("-----> http adding invoc req %s", invoc_id)
        self._http_requests[invoc_id] = http_request
        event = self.get_request_event(invoc_id)
        event.set()

    def add_http_invoc_response(self, invoc_id, http_response):
        logger.info("-----> grpc adding invoc res %s", invoc_id)
        self._http_responses[invoc_id] = http_response
        event = self.get_response_event(invoc_id)
        event.set()

    async def wait_and_get_http_invoc_request_async(self, invoc_id):
        logger.info("-----> grpc waiting for invoc req %s", invoc_id)
        await self._wait_for_event_async(invoc_id)
        return self._retrieve_and_clean_request(invoc_id)

    # TODO: the library shall tell whether its async or sync server
    def wait_and_get_http_invoc_request_sync(self, invoc_id):
        logger.info("-----> grpc waiting for invoc req %s", invoc_id)
        self._wait_for_event_sync(invoc_id)
        return self._retrieve_and_clean_request(invoc_id)

    async def wait_and_get_http_invoc_response_async(self, invoc_id):
        logger.info("-----> http waiting for invoc res %s", invoc_id)
        await self._wait_for_event_async(invoc_id, is_request=False)
        return self._retrieve_and_clean_response(invoc_id)

    def wait_and_get_http_invoc_response_sync(self, invoc_id):
        logger.info("-----> http waiting for invoc res %s", invoc_id)
        self._wait_for_event_sync(invoc_id, is_request=False)
        return self._retrieve_and_clean_response(invoc_id)

    async def _wait_for_event_async(self, invoc_id, is_request=True):
        event = self.get_request_event(invoc_id) if is_request else self.get_response_event(invoc_id)
        await event.wait()

    def _wait_for_event_sync(self, invoc_id, is_request=True):
        event = self.get_request_event(invoc_id) if is_request else self.get_response_event(invoc_id)
        event.wait()

    def _retrieve_and_clean_request(self, invoc_id):
        request = self._http_requests.pop(invoc_id, None)
        if request is not None:
            del self._http_requests_invoc_event[invoc_id]
            logger.info("-----> grpc got invoc req %s", invoc_id)
            return request
        else:
            logger.error("-----> No request found for invoc %s", invoc_id)

    def _retrieve_and_clean_response(self, invoc_id):
        response = self._http_responses.pop(invoc_id, None)
        if response is not None:
            del self._http_responses_invoc_event[invoc_id]
            logger.info("-----> got invoc res %s", invoc_id)
            return response
        else:
            logger.error("-----> No response found for invoc %s", invoc_id)


http_coordinator = HttpCoordinator()
