import argparse
import configparser
import functools
import logging
import os
import pathlib
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import requests
from tests.stein_tests.constants import PYAZURE_WEBHOST_DEBUG, \
    PYAZURE_WORKER_DIR, \
    PYAZURE_INTEGRATION_TEST, PROJECT_ROOT, STEIN_TESTS_ROOT, WORKER_CONFIG, \
    LOCALHOST, WORKER_PATH, HTTP_FUNCS_PATH

EXTENSIONS_PATH = PROJECT_ROOT / 'build' / 'extensions' / 'bin'
WEBHOST_DLL = "Microsoft.Azure.WebJobs.Script.WebHost.dll"
DEFAULT_WEBHOST_DLL_PATH = (
    PROJECT_ROOT / 'build' / 'webhost' / 'bin' / WEBHOST_DLL
)


# The template of host.json that will be applied to each test functions
HOST_JSON_TEMPLATE = """\
{
    "version": "2.0",
    "logging": {"logLevel": {"default": "Trace"}}
}
"""

EXTENSION_CSPROJ_TEMPLATE = """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netcoreapp3.1</TargetFramework>
    <WarningsAsErrors></WarningsAsErrors>
    <DefaultItemExcludes>**</DefaultItemExcludes>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.EventHubs"
     Version="5.0.0" />
    <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.EventGrid"
     Version="3.1.0" />
    <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.CosmosDB"
     Version="3.0.10" />
     <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.Storage"
     Version="4.0.5" />
     <PackageReference
      Include="Microsoft.Azure.WebJobs.Extensions.Storage.Blobs"
      Version="5.0.0" />
     <PackageReference
      Include="Microsoft.Azure.WebJobs.Extensions.Storage.Queues"
      Version="5.0.0" />
    <PackageReference
     Include="Microsoft.Azure.WebJobs.Script.ExtensionsMetadataGenerator"
     Version="1.1.3" />
  </ItemGroup>
</Project>
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


def is_env_var_true(env_key: str) -> bool:
    if os.getenv(env_key) is None:
        return False

    return is_true_like(os.environ[env_key])


def is_true_like(setting: str) -> bool:
    if setting is None:
        return False

    return setting.lower().strip() in ['1', 'true', 't', 'yes', 'y']


def remove_path(path):
    if path.is_symlink():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(str(path))
    elif path.exists():
        path.unlink()


def _symlink_dir(src, dst):
    remove_path(dst)

    if platform.system() == 'Windows':
        shutil.copytree(str(src), str(dst))
    else:
        dst.symlink_to(src, target_is_directory=True)


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
        try:
            self._proc.wait(20)
        except subprocess.TimeoutExpired:
            self._proc.kill()


def _find_open_port():
    with socket.socket() as s:
        s.bind((LOCALHOST, 0))
        s.listen(1)
        return s.getsockname()[1]


def popen_webhost(*, stdout, stderr, script_root=HTTP_FUNCS_PATH, port=None):
    testconfig = None
    if WORKER_CONFIG.exists():
        testconfig = configparser.ConfigParser()
        testconfig.read(WORKER_CONFIG)

    hostexe_args = []

    os.environ['AzureWebJobsFeatureFlags'] = 'EnableWorkerIndexing'

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
            '   `CORE_TOOLS_EXE_PATH` envrionment variable.',
            '',
            'Setting "export PYAZURE_WEBHOST_DEBUG=true" to get the full',
            'stdout and stderr from function host.'
        ]))

    worker_path = os.environ.get(PYAZURE_WORKER_DIR)
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
        'AzureWebJobsSecretStorageType': 'files',
        'FUNCTIONS_WORKER_RUNTIME': 'python'
    }

    # In E2E Integration mode, we should use the core tools worker
    # from the latest artifact instead of the azure_functions_worker module
    if is_env_var_true(PYAZURE_INTEGRATION_TEST):
        extra_env.pop('languageWorkers:python:workerDirectory')

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
    script_root = STEIN_TESTS_ROOT / script_dir if script_dir else \
        HTTP_FUNCS_PATH
    if stdout is None:
        if is_env_var_true(PYAZURE_WEBHOST_DEBUG):
            stdout = sys.stdout
        else:
            stdout = subprocess.DEVNULL

    port = _find_open_port()
    proc = popen_webhost(stdout=stdout, stderr=subprocess.STDOUT,
                         script_root=script_root, port=port)
    time.sleep(10)  # Giving host some time to start fully.
    addr = f'http://{LOCALHOST}:{port}'

    return _WebHostProxy(proc, addr)


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
                            and not is_env_var_true(PYAZURE_WEBHOST_DEBUG)):

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
        if is_env_var_true(PYAZURE_WEBHOST_DEBUG):
            cls.host_stdout = None
        else:
            cls.host_stdout = tempfile.NamedTemporaryFile('w+t')

        _setup_func_app(STEIN_TESTS_ROOT / script_dir)
        try:
            cls.webhost = start_webhost(script_dir=script_dir,
                                        stdout=cls.host_stdout)
        except Exception:
            _teardown_func_app(STEIN_TESTS_ROOT / script_dir)
            raise

    @classmethod
    def tearDownClass(cls):
        cls.webhost.close()
        cls.webhost = None

        if cls.host_stdout is not None:
            cls.host_stdout.close()
            cls.host_stdout = None

        script_dir = pathlib.Path(cls.get_script_dir())
        _teardown_func_app(STEIN_TESTS_ROOT / script_dir)

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
                    f'Captured WebHost stdout from {self.host_stdout.name} '
                    f':\n{self.host_out}')
            finally:
                if test_exception is not None:
                    raise test_exception


def _setup_func_app(app_root):
    extensions = app_root / 'bin'
    host_json = app_root / 'host.json'
    extensions_csproj_file = app_root / 'extensions.csproj'

    if not os.path.isfile(host_json):
        with open(host_json, 'w') as f:
            f.write(HOST_JSON_TEMPLATE)

    if not os.path.isfile(extensions_csproj_file):
        with open(extensions_csproj_file, 'w') as f:
            f.write(EXTENSION_CSPROJ_TEMPLATE)

    _symlink_dir(EXTENSIONS_PATH, extensions)


def _teardown_func_app(app_root):
    extensions = app_root / 'bin'
    host_json = app_root / 'host.json'
    extensions_csproj_file = app_root / 'extensions.csproj'
    extensions_obj_file = app_root / 'obj'

    for path in (extensions, host_json, extensions_csproj_file,
                 extensions_obj_file):
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
