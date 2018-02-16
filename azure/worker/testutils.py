import argparse
import configparser
import os
import pathlib
import subprocess
import sys
import time

import requests


FUNCS_PATH = pathlib.Path(__file__).parent / 'tests' / 'functions'
WORKER_PATH = pathlib.Path(__file__).parent.parent.parent
WORKER_CONFIG = WORKER_PATH / '.testconfig'


class WebHost:
    def __init__(self, proc, addr):
        self._proc = proc
        self._addr = addr

    def request(self, meth, funcname, *args, **kwargs):
        request_method = getattr(requests, meth.lower())
        return request_method(self._addr + '/api/' + funcname, *args, **kwargs)

    def stop(self):
        self._proc.terminate()


def popen_webhost(*, stdout, stderr, script_root=FUNCS_PATH):
    testconfig = None
    if WORKER_CONFIG.exists():
        testconfig = configparser.ConfigParser()
        testconfig.read(WORKER_CONFIG)

    if 'PYAZURE_WEBHOST_DLL' in os.environ:
        dll = os.environ['PYAZURE_WEBHOST_DLL']
    elif testconfig is not None:
        dll = testconfig['webhost'].get('dll')

    if not dll or not pathlib.Path(dll).exists():
        raise RuntimeError('\n'.join([
            f'Unable to locate "WebHost.dll". Please do one of the following:',
            f' * set PYAZURE_WEBHOST_DLL environment variable to WebHost.dll;',
            f' * create {WORKER_CONFIG} file in with the following structure:',
            f'   [webhost]',
            f'   dll = /path/to/my/Microsoft.Azure.WebJobs.Script.WebHost.dll',
        ]))

    return subprocess.Popen(
        ['dotnet', dll],
        cwd=script_root,
        env={
            **os.environ,
            'AzureWebJobsScriptRoot': script_root,
            'workers:config:path': WORKER_PATH,
            'workers:python:path': WORKER_PATH / 'python' / 'worker.py',
            'host:logger:consoleLoggingMode': 'always',
        },
        stdout=stdout,
        stderr=stderr)


def start_webhost():
    proc = popen_webhost(stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    while True:
        line = proc.stdout.readline()
        if b'Now listening on: ' in line:
            addr = line[len(b'Now listening on: '):]
            break

    addr = addr.decode('ascii').strip()

    for n in range(10):
        r = requests.get(addr + '/api/return_str')
        if r.status_code == 200:
            break
        time.sleep(0.5)

    if r.status_code != 200:
        proc.terminate()
        raise RuntimeError('could not start the webworker')

    return WebHost(proc, addr)


def main():
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
    main()
