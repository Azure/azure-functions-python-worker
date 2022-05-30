# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import asyncio
import pathlib
import typing
import sys

from azure_functions_worker import protos, testutils, dispatcher


class _MockWebHostWithWorkerController:

    def __init__(self, scripts_dir: pathlib.PurePath, event_loop):
        self._event_loop = event_loop
        self._host: typing.Optional[testutils._MockWebHost] = None
        self._scripts_dir: pathlib.PurePath = scripts_dir
        self._worker: typing.Optional[dispatcher.Dispatcher] = None

    async def __aenter__(self) -> typing.Tuple[testutils._MockWebHost, dispatcher.Dispatcher]:
        loop = self._event_loop
        self._host = testutils._MockWebHost(loop, self._scripts_dir)

        await self._host.start()

        self._worker = await dispatcher.\
            Dispatcher.connect(testutils.LOCALHOST, self._host._port,
                               self._host.worker_id, self._host.request_id,
                               connect_timeout=5.0)

        self._worker_task = loop.create_task(self._worker.dispatch_forever())

        done, pending = await asyncio. \
            wait([self._host._connected_fut, self._worker_task],
                 return_when=asyncio.FIRST_COMPLETED)

        # noinspection PyBroadException
        try:
            if self._worker_task in done:
                self._worker_task.result()

            if self._host._connected_fut not in done:
                raise RuntimeError('could not start a worker thread')
        except Exception:
            try:
                await self._host.close()
                self._worker.stop()
            finally:
                raise

        return self._host, self._worker

    async def __aexit__(self, *exc):
        if not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        self._worker_task = None
        self._worker = None

        await self._host.close()
        self._host = None

def start_mockhost_with_worker(event_loop, script_root=testutils.FUNCS_PATH):
    scripts_dir = testutils.TESTS_ROOT / script_root
    if not (scripts_dir.exists() and scripts_dir.is_dir()):
        raise RuntimeError(
            f'invalid script_root argument: '
            f'{scripts_dir} directory does not exist')

    sys.path.append(str(scripts_dir))

    return _MockWebHostWithWorkerController(scripts_dir, event_loop)

def test_invoke_function_benchmark(aio_benchmark, event_loop):
    async def invoke_function():
        wc = start_mockhost_with_worker(event_loop)
        async with wc as (host, worker):
            await host.load_function('return_http')
            
            func = host._available_functions['return_http']
            invocation_id = host.make_id()
            input_data = [protos.ParameterBinding(
                            name='req',
                            data=protos.TypedData(
                                http=protos.RpcHttp(
                                    method='GET')))]
            message = protos.StreamingMessage(
                        invocation_request=protos.InvocationRequest(
                            invocation_id=invocation_id,
                            function_id=func.id,
                            input_data=input_data,
                            trigger_metadata={},
                        )
                    )
            for _ in range(1000):
                event_loop.create_task(worker._handle__invocation_request(message))
    
    aio_benchmark(invoke_function)

