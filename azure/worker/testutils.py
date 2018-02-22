"""Unittest helpers.

All functions in this file should be considered private APIs,
and can be changed without a notice.
"""

import argparse
import asyncio
import concurrent.futures
import configparser
import functools
import inspect
import json
import os
import queue
import pathlib
import socket
import subprocess
import sys
import time
import typing
import unittest
import uuid

import grpc
import requests

from . import aio_compat
from . import dispatcher
from . import protos


TESTS_ROOT = pathlib.Path(__file__).parent / 'tests'
FUNCS_PATH = TESTS_ROOT / 'http_functions'
WORKER_PATH = pathlib.Path(__file__).parent.parent.parent
WORKER_CONFIG = WORKER_PATH / '.testconfig'


class AsyncTestCaseMeta(type(unittest.TestCase)):

    def __new__(mcls, name, bases, ns):
        for attrname, attr in ns.items():
            if (attrname.startswith('test_') and
                    inspect.iscoroutinefunction(attr)):
                ns[attrname] = mcls._sync_wrap(attr)

        return super().__new__(mcls, name, bases, ns)

    @staticmethod
    def _sync_wrap(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return aio_compat.run(func(*args, **kwargs))
        return wrapper


class AsyncTestCase(unittest.TestCase, metaclass=AsyncTestCaseMeta):
    pass


class WebHostTestCase(unittest.TestCase):

    @classmethod
    def get_script_dir(cls):
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        script_dir = cls.get_script_dir()
        cls.webhost = start_webhost(script_dir=script_dir)

    @classmethod
    def tearDownClass(cls):
        cls.webhost.close()
        cls.webhost = None


class _MockWebHostServicer(protos.FunctionRpcServicer):

    _STOP = object()

    def __init__(self, host):
        self._host = host

    def EventStream(self, client_response_iterator, context):
        client_response = next(client_response_iterator)
        rtype = client_response.WhichOneof('content')
        try:
            if rtype != 'start_stream':
                raise AssertionError(
                    f'unexpected {rtype!r} initial message from the worker')

            if client_response.start_stream.worker_id != self._host.worker_id:
                raise AssertionError(f'worker_id mismatch')

        except Exception as ex:
            self._host._loop.call_soon_threadsafe(
                self._host._connected_fut.set_exception, ex)
            return
        else:
            self._host._loop.call_soon_threadsafe(
                self._host._connected_fut.set_result, True)

        while True:
            message, wait_for = self._host._in_queue.get()
            if message is self._STOP:
                return

            yield message

            if wait_for is None:
                continue

            response = None
            logs = []

            for client_response in client_response_iterator:
                rtype = client_response.WhichOneof('content')
                unpacked = getattr(client_response, rtype)

                if rtype == wait_for:
                    response = unpacked
                    break
                elif rtype == 'rpc_log':
                    logs.append(unpacked)
                else:
                    raise RuntimeError(
                        f'unexpected response from worker: '
                        f'expected to receive {wait_for!r}, got {rtype!r}')

            self._host._loop.call_soon_threadsafe(
                self._host._out_aqueue.put_nowait,
                _WorkerResponseMessages(response, logs))


class _WebHostFunction(typing.NamedTuple):
    id: str
    name: str
    desc: dict
    script: pathlib.Path


class _WorkerResponseMessages(typing.NamedTuple):
    response: object
    logs: list


class _MockWebHost:

    def __init__(self, loop, scripts_dir):
        self._loop = loop
        self._scripts_dir = scripts_dir

        self._available_functions = {}
        self._read_available_functions()

        self._connected_fut = loop.create_future()
        self._in_queue = queue.Queue()
        self._out_aqueue = asyncio.Queue(loop=self._loop)
        self._threadpool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1)
        self._server = grpc.server(self._threadpool)
        self._servicer = _MockWebHostServicer(self)
        protos.add_FunctionRpcServicer_to_server(self._servicer, self._server)
        self._port = self._server.add_insecure_port('127.0.0.1:0')

        self._worker_id = self.make_id()
        self._request_id = self.make_id()

    def make_id(self):
        return str(uuid.uuid4())

    @property
    def worker_id(self):
        return self._worker_id

    @property
    def request_id(self):
        return self._request_id

    async def load_function(self, name):
        if name not in self._available_functions:
            raise RuntimeError(f'cannot load function {name}')

        func = self._available_functions[name]

        bindings = {}
        for b in func.desc['bindings']:
            direction = getattr(protos.BindingInfo, b['direction'])
            bindings[b['name']] = protos.BindingInfo(
                type=b['type'],
                direction=direction)

        r = await self.communicate(
            protos.StreamingMessage(
                function_load_request=protos.FunctionLoadRequest(
                    function_id=func.id,
                    metadata=protos.RpcFunctionMetadata(
                        name=func.name,
                        directory=os.path.dirname(func.script),
                        script_file=func.script,
                        bindings=bindings))),
            wait_for='function_load_response')

        return func.id, r

    async def invoke_function(
            self, name, input_data: typing.List[protos.ParameterBinding]):

        if name not in self._available_functions:
            raise RuntimeError(f'cannot load function {name}')

        func = self._available_functions[name]
        invocation_id = self.make_id()

        r = await self.communicate(
            protos.StreamingMessage(
                invocation_request=protos.InvocationRequest(
                    invocation_id=invocation_id,
                    function_id=func.id,
                    input_data=input_data)),
            wait_for='invocation_response')

        return invocation_id, r

    async def send(self, message):
        self._in_queue.put_nowait((message, None))

    async def communicate(self, message, *, wait_for):
        self._in_queue.put_nowait((message, wait_for))
        return await self._out_aqueue.get()

    async def _start(self):
        self._server.start()

    async def _close(self):
        self._in_queue.put_nowait((_MockWebHostServicer._STOP, None))
        self._server.stop(1)

    def _read_available_functions(self):
        for fd in self._scripts_dir.iterdir():
            if not fd.is_dir():
                continue

            fjson_fn = fd / 'function.json'
            if not fjson_fn.exists():
                continue

            try:
                with open(fjson_fn, 'rt') as f:
                    fjson = json.loads(f.read())

                fscript = fjson['scriptFile']
                fscript_fn = fd / fscript
                if not fscript_fn.exists():
                    raise RuntimeError(f'{fscript_fn} path does not exist')

            except Exception as ex:
                raise RuntimeError(
                    f'could not load function {fd.name}') from ex

            fn = _WebHostFunction(
                name=fd.name, desc=fjson, script=str(fscript_fn),
                id=self.make_id())

            self._available_functions[fn.name] = fn


class _MockWebHostController:

    def __init__(self, scripts_dir):
        self._host = None
        self._scripts_dir = scripts_dir
        self._worker = None

    async def __aenter__(self):
        loop = aio_compat.get_running_loop()
        self._host = _MockWebHost(loop, self._scripts_dir)

        await self._host._start()

        self._worker = await dispatcher.Dispatcher.connect(
            '127.0.0.1', self._host._port,
            self._host.worker_id, self._host.request_id,
            connect_timeout=5.0)

        self._worker_task = loop.create_task(self._worker.dispatch_forever())

        done, pending = await asyncio.wait(
            [self._host._connected_fut, self._worker_task],
            return_when=asyncio.FIRST_COMPLETED)

        try:
            if self._worker_task in done:
                self._worker_task.result()

            if self._host._connected_fut not in done:
                raise RuntimeError('could not start a worker thread')
        except Exception:
            try:
                self._host._close()
                self._worker.stop()
            finally:
                raise

        return self._host

    async def __aexit__(self, *exc):
        if not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        self._worker_task = None
        self._worker = None

        await self._host._close()
        self._host = None


def start_mockhost(*, script_root='http_functions'):
    tests_dir = pathlib.Path(__file__).parent / 'tests'
    scripts_dir = tests_dir / script_root
    if not scripts_dir.exists() or not scripts_dir.is_dir():
        raise RuntimeError(
            f'invalid script_root argument: '
            f'{scripts_dir} directory does not exist')

    return _MockWebHostController(scripts_dir)


class _WebHostProxy:

    def __init__(self, proc, addr):
        self._proc = proc
        self._addr = addr

    def request(self, meth, funcname, *args, **kwargs):
        request_method = getattr(requests, meth.lower())
        return request_method(self._addr + '/api/' + funcname, *args, **kwargs)

    def close(self):
        try:
            self._proc.stdout.close()
            self._proc.stderr.close()
        finally:
            self._proc.terminate()
            self._proc.wait()


def _find_open_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        return s.getsockname()[1]


def popen_webhost(*, stdout, stderr, script_root=FUNCS_PATH, port=None):
    testconfig = None
    if WORKER_CONFIG.exists():
        testconfig = configparser.ConfigParser()
        testconfig.read(WORKER_CONFIG)

    dll = os.environ.get('PYAZURE_WEBHOST_DLL')
    if not dll and testconfig:
        dll = testconfig['webhost'].get('dll')

    if not dll or not pathlib.Path(dll).exists():
        raise RuntimeError('\n'.join([
            f'Unable to locate "WebHost.dll". Please do one of the following:',
            f' * set PYAZURE_WEBHOST_DLL environment variable to WebHost.dll;',
            f' * create {WORKER_CONFIG} file in with the following structure:',
            f'   [webhost]',
            f'   dll = /path/to/my/Microsoft.Azure.WebJobs.Script.WebHost.dll',
        ]))

    # Paths from environment might contain trailing or leading whitespace.
    dll = dll.strip()

    worker_path = os.environ.get('PYAZURE_WORKER_DIR')
    if not worker_path:
        worker_path = WORKER_PATH
    else:
        worker_path = pathlib.Path(worker_path)

    if not worker_path.exists():
        raise RuntimeError(f'Worker path {worker_path} does not exist')

    # Casting to strings is necessary because Popen doesn't like
    # path objects there on Windows.
    extra_env = {
        'AzureWebJobsScriptRoot': str(script_root),
        'workers:config:path': str(worker_path),
        'workers:python:path': str(worker_path / 'python' / 'worker.py'),
        'host:logger:consoleLoggingMode': 'always',
    }

    if port is not None:
        extra_env['ASPNETCORE_URLS'] = f'http://*:{port}'

    return subprocess.Popen(
        ['dotnet', dll],
        cwd=script_root,
        env={
            **os.environ,
            **extra_env,
        },
        stdout=stdout,
        stderr=stderr)


def start_webhost(*, script_dir=None):
    if script_dir:
        script_root = TESTS_ROOT / script_dir
    else:
        script_root = FUNCS_PATH

    port = _find_open_port()
    proc = popen_webhost(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         script_root=script_root, port=port)

    addr = f'http://127.0.0.1:{port}'

    for n in range(10):
        try:
            r = requests.get(f'{addr}/api/ping')
            if 200 <= r.status_code < 300:
                break
        except requests.exceptions.ConnectionError:
            pass

        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError('could not start the webworker')

    return _WebHostProxy(proc, addr)


def _main():
    parser = argparse.ArgumentParser(description='Run a Python worker.')
    parser.add_argument(
        '--script-root',
        dest='script_root',
        default=FUNCS_PATH,
        help=f'defaults to {FUNCS_PATH}')

    args = parser.parse_args()

    host = popen_webhost(
        stdout=sys.stdout, stderr=sys.stderr,
        script_root=os.path.abspath(args.script_root))
    try:
        host.wait()
    finally:
        host.terminate()


if __name__ == '__main__':
    _main()
