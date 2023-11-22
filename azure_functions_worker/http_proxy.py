import asyncio

from .logging import (
    logger
)

import threading
from concurrent.futures import Future


class HttpCoordinator:
    def __init__(self):
        if not self._initialized:
            self._http_requests = {}
            self._http_responses = {}
            self._http_requests_invoc_event = {}
            self._http_responses_invoc_event = {}
            self._initialized = True

    # making this class singleton
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HttpCoordinator, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def get_request_event(self, invoc_id):
        if invoc_id not in self._http_requests_invoc_event:
            self._http_requests_invoc_event[invoc_id] = asyncio.Event()
        return self._http_requests_invoc_event[invoc_id]

    async def add_http_invoc_request(self, invoc_id, http_request):
        logger.info("-----> http adding invoc req %s", invoc_id)
        self._http_requests[invoc_id] = http_request
        event = self.get_request_event(invoc_id)
        event.set()

    async def wait_and_get_http_invoc_request(self, invoc_id):
        logger.info("-----> grpc wating for invoc req %s", invoc_id)
        event = self.get_request_event(invoc_id)
        await event.wait()
        request = self._http_requests[invoc_id]
        del self._http_requests[invoc_id]
        del self._http_requests_invoc_event[invoc_id]
        logger.info("-----> grpc got invoc req %s", invoc_id)
        return request

    def get_response_event(self, invoc_id):
        if invoc_id not in self._http_responses_invoc_event:
            self._http_responses_invoc_event[invoc_id] = asyncio.Event()
        return self._http_responses_invoc_event[invoc_id]

    async def add_http_invoc_response(self, invoc_id, http_response):
        logger.info("-----> grpc adding invoc res %s", invoc_id)
        self._http_responses[invoc_id] = http_response
        event = self.get_response_event(invoc_id)
        event.set()

    async def wait_and_get_http_invoc_response(self, invoc_id):
        logger.info("-----> http waiting for invoc res %s", invoc_id)
        event = self.get_response_event(invoc_id)
        await event.wait()
        response = self._http_responses[invoc_id]
        del self._http_responses[invoc_id]
        del self._http_responses_invoc_event[invoc_id]
        logger.info("-----> got invoc res %s", invoc_id)
        return response


http_coordinator = HttpCoordinator()