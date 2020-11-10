# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
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
import logging
import os
import pathlib
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import typing
import unittest
import uuid

import grpc
import requests

from azure_functions_worker._thirdparty import aio_compat
from . import dispatcher
from . import protos
from .constants import PYAZURE_WEBHOST_DEBUG
from .utils.common import is_envvar_true

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
E2E_TESTS_FOLDER = pathlib.Path('endtoend')
E2E_TESTS_ROOT = TESTS_ROOT / E2E_TESTS_FOLDER
UNIT_TESTS_FOLDER = pathlib.Path('unittests')
UNIT_TESTS_ROOT = TESTS_ROOT / UNIT_TESTS_FOLDER
WEBHOST_DLL = "Microsoft.Azure.WebJobs.Script.WebHost.dll"
DEFAULT_WEBHOST_DLL_PATH = PROJECT_ROOT / 'build' / 'webhost' / WEBHOST_DLL
EXTENSIONS_PATH = PROJECT_ROOT / 'build' / 'extensions' / 'bin'
FUNCS_PATH = TESTS_ROOT / UNIT_TESTS_FOLDER / 'http_functions'
WORKER_PATH = PROJECT_ROOT / 'python' / 'test'
WORKER_CONFIG = PROJECT_ROOT / '.testconfig'
ON_WINDOWS = platform.system() == 'Windows'
LOCALHOST = "127.0.0.1"

HOST_JSON_TEMPLATE = """\
{
    "version": "2.0",
    "logging": {
        "logLevel": {
           "default": "Trace"
        }
    },
    "http": {
        "routePrefix": "api"
    },
    "swagger": {
        "enabled": true
    },
    "eventHub": {
        "maxBatchSize": 1000,
        "prefetchCount": 1000,
        "batchCheckpointFrequency": 1
    },
    "functionTimeout": "00:05:00"
}
"""

SECRETS_TEMPLATE = """\
{
  "masterKey": {
    "name": "master",
    "value": "testMasterKey",
    "encrypted": false
  },
  "functionKeys": [
    {
      "name": "default",
      "value": "testFunctionKey",
      "encrypted": false
    }
  ],
   "systemKeys": [
    {
      "name": "eventgridextensionconfig_extension",
      "value": "testSystemKey",
      "encrypted": false
    }
  ],
  "hostName": null,
  "instanceId": "0000000000000000000000001C69C103",
  "source": "runtime"
}
"""


class AsyncTestCaseMeta(type(unittest.TestCase)):

    def __new__(mcls, name, bases, ns):
        for attrname, attr in ns.items():
            if (attrname.startswith('test_')
               and inspect.iscoroutinefunction(attr)):
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


class WebHostTestCaseMeta(type(unittest.TestCase)):

    def __new__(mcls, name, bases, dct):
        for attrname, attr in dct.items():
            if attrname.startswith('test_') and callable(attr):
                test_case = attr
                check_log_name = attrname.replace('test_', 'check_log_', 1)
                check_log_case = dct.get(check_log_name)

                @functools.wraps(test_case)
                def wrapper(self, *args, __meth__=test_case,
                            __check_log__=check_log_case, **kwargs):
                    if (__check_log__ is not None
                            and callable(__check_log__)
                            and not is_envvar_true(PYAZURE_WEBHOST_DEBUG)):

                        # Check logging output for unit test scenarios
                        result = self._run_test(__meth__, *args, **kwargs)

                        # Trim off host output timestamps
                        host_output = getattr(self, 'host_out', '')
                        output_lines = host_output.splitlines()
                        ts_re = r"^\[\d+(\/|-)\d+(\/|-)\d+T*\d+\:\d+\:\d+.*(" \
                                r"A|P)*M*\]"
                        output = list(map(lambda s:
                                          re.sub(ts_re, '', s).strip(),
                                          output_lines))

                        # Execute check_log_ test cases
                        self._run_test(__check_log__, host_out=output)
                        return result
                    else:
                        # Check normal unit test
                        return self._run_test(__meth__, *args, **kwargs)

                dct[attrname] = wrapper

        return super().__new__(mcls, name, bases, dct)


class WebHostTestCase(unittest.TestCase, metaclass=WebHostTestCaseMeta):
    """Base class for integration tests that need a WebHost.

    In addition to automatically starting up a WebHost instance,
    this test case class logs WebHost stdout/stderr in case
    a unit test fails.

    You can write two sets of test - test_* and check_log_* tests.

    test_ABC - Unittest
    check_log_ABC - Check logs generated during the execution of test_ABC.
    """
    host_stdout_logger = logging.getLogger('webhosttests')

    @classmethod
    def get_script_dir(cls):
        raise NotImplementedError

    @classmethod
    def setUpClass(cls):
        script_dir = pathlib.Path(cls.get_script_dir())
        if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
            cls.host_stdout = None
        else:
            cls.host_stdout = tempfile.NamedTemporaryFile('w+t')

        _setup_func_app(TESTS_ROOT / script_dir)
        try:
            cls.webhost = start_webhost(script_dir=script_dir,
                                        stdout=cls.host_stdout)
        except Exception:
            _teardown_func_app(TESTS_ROOT / script_dir)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.webhost.close()
        cls.webhost = None

        if cls.host_stdout is not None:
            cls.host_stdout.close()
            cls.host_stdout = None

        script_dir = pathlib.Path(cls.get_script_dir())
        _teardown_func_app(TESTS_ROOT / script_dir)

    def _run_test(self, test, *args, **kwargs):
        if self.host_stdout is None:
            test(self, *args, **kwargs)
        else:
            # Discard any host stdout left from the previous test or
            # from the setup.
            self.host_stdout.read()
            last_pos = self.host_stdout.tell()

            test_exception = None
            try:
                test(self, *args, **kwargs)
            except Exception as e:
                test_exception = e

            try:
                self.host_stdout.seek(last_pos)
                self.host_out = self.host_stdout.read()
                self.host_stdout_logger.error(
                    f'Captured WebHost stdout:\n{self.host_out}')
            finally:
                if test_exception is not None:
                    raise test_exception


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
                raise AssertionError('worker_id mismatch')

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
        self._port = self._server.add_insecure_port(f'{LOCALHOST}:0')

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

            data_type_v = b.get('dataType')
            if not data_type_v:
                data_type = protos.BindingInfo.undefined
            elif data_type_v == 'binary':
                data_type = protos.BindingInfo.binary
            elif data_type_v == 'string':
                data_type = protos.BindingInfo.string
            elif data_type_v == 'stream':
                data_type = protos.BindingInfo.stream
            else:
                raise RuntimeError(f'invalid dataType: {data_type_v!r}')

            bindings[b['name']] = protos.BindingInfo(
                type=b['type'],
                data_type=data_type,
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
            self,
            name,
            input_data: typing.List[protos.ParameterBinding],
            metadata: typing.Optional[
                typing.Mapping[str, protos.TypedData]] = None):

        if metadata is None:
            metadata = {}

        if name not in self._available_functions:
            raise RuntimeError(f'cannot load function {name}')

        func = self._available_functions[name]
        invocation_id = self.make_id()

        r = await self.communicate(
            protos.StreamingMessage(
                invocation_request=protos.InvocationRequest(
                    invocation_id=invocation_id,
                    function_id=func.id,
                    input_data=input_data,
                    trigger_metadata=metadata,
                )
            ),
            wait_for='invocation_response')

        return invocation_id, r

    async def reload_environment(
        self,
        environment: typing.Dict[str, str],
        function_project_path: str = '/home/site/wwwroot'
    ) -> protos.FunctionEnvironmentReloadResponse:

        request_content = protos.FunctionEnvironmentReloadRequest(
            function_app_directory=function_project_path,
            environment_variables={
                k.encode(): v.encode() for k, v in environment.items()
            }
        )

        r = await self.communicate(
            protos.StreamingMessage(
                function_environment_reload_request=request_content
            ),
            wait_for='function_environment_reload_response'
        )

        return r

    async def send(self, message):
        self._in_queue.put_nowait((message, None))

    async def communicate(self, message, *, wait_for):
        self._in_queue.put_nowait((message, wait_for))
        return await self._out_aqueue.get()

    async def start(self):
        self._server.start()

    async def close(self):
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

    def __init__(self, scripts_dir: pathlib.PurePath):
        self._host: typing.Optional[_MockWebHost] = None
        self._scripts_dir: pathlib.PurePath = scripts_dir
        self._worker: typing.Optional[dispatcher.Dispatcher] = None

    async def __aenter__(self) -> _MockWebHost:
        loop = aio_compat.get_running_loop()
        self._host = _MockWebHost(loop, self._scripts_dir)

        await self._host.start()

        self._worker = await dispatcher. \
            Dispatcher.connect(LOCALHOST, self._host._port,
                               self._host.worker_id,
                               self._host.request_id, connect_timeout=5.0)

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

        await self._host.close()
        self._host = None


def start_mockhost(*, script_root=FUNCS_PATH):
    tests_dir = TESTS_ROOT
    scripts_dir = tests_dir / script_root
    if not (scripts_dir.exists() and scripts_dir.is_dir()):
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
        params = dict(kwargs.pop('params', {}))
        if 'code' not in params:
            params['code'] = 'testFunctionKey'
        return request_method(self._addr + '/api/' + funcname,
                              *args, params=params, **kwargs)

    def close(self):
        if self._proc.stdout:
            self._proc.stdout.close()
        if self._proc.stderr:
            self._proc.stderr.close()

        self._proc.terminate()
        self._proc.wait()


def _find_open_port():
    with socket.socket() as s:
        s.bind((LOCALHOST, 0))
        s.listen(1)
        return s.getsockname()[1]


def popen_webhost(*, stdout, stderr, script_root=FUNCS_PATH, port=None):
    testconfig = None
    if WORKER_CONFIG.exists():
        testconfig = configparser.ConfigParser()
        testconfig.read(WORKER_CONFIG)

    hostexe_args = []

    # If we want to use core-tools
    coretools_exe = os.environ.get('CORE_TOOLS_EXE_PATH')
    if coretools_exe:
        coretools_exe = coretools_exe.strip()
        if pathlib.Path(coretools_exe).exists():
            hostexe_args = [str(coretools_exe), 'host', 'start']
            if port is not None:
                hostexe_args.extend(['--port', str(port)])

    # If we need to use Functions host directly
    if not hostexe_args:
        dll = os.environ.get('PYAZURE_WEBHOST_DLL')
        if not dll and testconfig and testconfig.has_section('webhost'):
            dll = testconfig['webhost'].get('dll')

        if dll:
            # Paths from environment might contain trailing
            # or leading whitespace.
            dll = dll.strip()

        if not dll:
            dll = DEFAULT_WEBHOST_DLL_PATH

            os.makedirs(dll.parent / 'Secrets', exist_ok=True)
            with open(dll.parent / 'Secrets' / 'host.json', 'w') as f:
                secrets = SECRETS_TEMPLATE

                f.write(secrets)

        if dll and pathlib.Path(dll).exists():
            hostexe_args = ['dotnet', str(dll)]

    if not hostexe_args:
        raise RuntimeError('\n'.join([
            'Unable to locate Azure Functions Host binary.',
            'Please do one of the following:',
            ' * run the following command from the root folder of',
            '   the project:',
            '',
            f'       $ {sys.executable} setup.py webhost',
            '',
            ' * or download or build the Azure Functions Host and'
            '   then write the full path to WebHost.dll'
            '   into the `PYAZURE_WEBHOST_DLL` environment variable.',
            '   Alternatively, you can create the',
            f'   {WORKER_CONFIG.name} file in the root folder',
            '   of the project with the following structure:',
            '',
            '      [webhost]',
            '      dll = /path/Microsoft.Azure.WebJobs.Script.WebHost.dll',
            ' * or download Azure Functions Core Tools binaries and',
            '   then write the full path to func.exe into the ',
            '   `CORE_TOOLS_PATH` envrionment variable.'
        ]))

    worker_path = os.environ.get('PYAZURE_WORKER_DIR')
    worker_path = WORKER_PATH if not worker_path else pathlib.Path(worker_path)
    if not worker_path.exists():
        raise RuntimeError(f'Worker path {worker_path} does not exist')

    # Casting to strings is necessary because Popen doesn't like
    # path objects there on Windows.
    extra_env = {
        'AzureWebJobsScriptRoot': str(script_root),
        'languageWorkers:python:workerDirectory': str(worker_path),
        'host:logger:consoleLoggingMode': 'always',
        'AZURE_FUNCTIONS_ENVIRONMENT': 'development',
        'AzureWebJobsSecretStorageType': 'files'
    }

    if testconfig and 'azure' in testconfig:
        st = testconfig['azure'].get('storage_key')
        if st:
            extra_env['AzureWebJobsStorage'] = st

        cosmos = testconfig['azure'].get('cosmosdb_key')
        if cosmos:
            extra_env['AzureWebJobsCosmosDBConnectionString'] = cosmos

        eventhub = testconfig['azure'].get('eventhub_key')
        if eventhub:
            extra_env['AzureWebJobsEventHubConnectionString'] = eventhub

        servicebus = testconfig['azure'].get('servicebus_key')
        if servicebus:
            extra_env['AzureWebJobsServiceBusConnectionString'] = servicebus

        eventgrid_topic_uri = testconfig['azure'].get('eventgrid_topic_uri')
        if eventgrid_topic_uri:
            extra_env['AzureWebJobsEventGridTopicUri'] = eventgrid_topic_uri

        eventgrid_topic_key = testconfig['azure'].get('eventgrid_topic_key')
        if eventgrid_topic_key:
            extra_env['AzureWebJobsEventGridConnectionKey'] = \
                eventgrid_topic_key

    if port is not None:
        extra_env['ASPNETCORE_URLS'] = f'http://*:{port}'

    return subprocess.Popen(
        hostexe_args,
        cwd=script_root,
        env={
            **os.environ,
            **extra_env,
        },
        stdout=stdout,
        stderr=stderr)


def start_webhost(*, script_dir=None, stdout=None):
    script_root = TESTS_ROOT / script_dir if script_dir else FUNCS_PATH
    if stdout is None:
        if is_envvar_true(PYAZURE_WEBHOST_DEBUG):
            stdout = sys.stdout
        else:
            stdout = subprocess.DEVNULL

    port = _find_open_port()
    proc = popen_webhost(stdout=stdout, stderr=subprocess.STDOUT,
                         script_root=script_root, port=port)
    time.sleep(10)  # Giving host some time to start fully.

    addr = f'http://{LOCALHOST}:{port}'
    for _ in range(10):
        try:
            r = requests.get(f'{addr}/api/ping',
                             params={'code': 'testFunctionKey'})
            # Give the host a bit more time to settle
            time.sleep(2)

            if 200 <= r.status_code < 300:
                # Give the host a bit more time to settle
                time.sleep(2)
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    else:
        proc.terminate()
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise RuntimeError('could not start the webworker')

    return _WebHostProxy(proc, addr)


def create_dummy_dispatcher():
    dummy_event_loop = asyncio.new_event_loop()
    disp = dispatcher.Dispatcher(
        dummy_event_loop, LOCALHOST, 0,
        'test_worker_id', 'test_request_id',
        1.0, 1000)
    dummy_event_loop.close()
    return disp


def retryable_test(
    number_of_retries: int,
    interval_sec: int,
    expected_exception: type = Exception
):
    def decorate(func):
        def call(*args, **kwargs):
            retries = number_of_retries
            while True:
                try:
                    return func(*args, **kwargs)
                except expected_exception as e:
                    retries -= 1
                    if retries <= 0:
                        raise e

                time.sleep(interval_sec)
        return call
    return decorate


def remove_path(path):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def _symlink_dir(src, dst):
    remove_path(dst)

    if ON_WINDOWS:
        shutil.copytree(str(src), str(dst))
    else:
        dst.symlink_to(src, target_is_directory=True)


def _setup_func_app(app_root):
    extensions = app_root / 'bin'
    ping_func = app_root / 'ping'
    host_json = app_root / 'host.json'

    if not os.path.isfile(host_json):
        with open(host_json, 'w') as f:
            f.write(HOST_JSON_TEMPLATE)

    _symlink_dir(TESTS_ROOT / 'common' / 'ping', ping_func)
    _symlink_dir(EXTENSIONS_PATH, extensions)


def _teardown_func_app(app_root):
    extensions = app_root / 'bin'
    ping_func = app_root / 'ping'
    host_json = app_root / 'host.json'

    for path in (extensions, ping_func, host_json):
        remove_path(path)


def _main():
    parser = argparse.ArgumentParser(description='Run a Python worker.')
    parser.add_argument('scriptroot',
                        help='directory with functions to load')

    args = parser.parse_args()

    app_root = pathlib.Path(args.scriptroot)
    _setup_func_app(app_root)

    host = popen_webhost(
        stdout=sys.stdout, stderr=sys.stderr,
        script_root=os.path.abspath(args.scriptroot))
    try:
        host.wait()
    finally:
        host.terminate()
        _teardown_func_app()


if __name__ == '__main__':
    _main()
