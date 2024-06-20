import os
import re
import subprocess
import sys
import typing
import unittest
import uuid
from dataclasses import dataclass
from pathlib import Path
from time import sleep

import requests

from tests.utils.constants import PROJECT_ROOT, TESTS_ROOT

_DOCKER_PATH = "DOCKER_PATH"
_DOCKER_DEFAULT_PATH = "docker"
_HOST_VERSION = "4"
_docker_cmd = os.getenv(_DOCKER_PATH, _DOCKER_DEFAULT_PATH)
_addr = ""
_python_version = f'{sys.version_info.major}.{sys.version_info.minor}'
_libraries_path = '.python_packages/lib/site-packages'
_uuid = str(uuid.uuid4())
_MESH_IMAGE_URL = "https://mcr.microsoft.com/v2/azure-functions/mesh/tags/list"
_MESH_IMAGE_REPO = "mcr.microsoft.com/azure-functions/mesh"
_IMAGE_URL = "https://mcr.microsoft.com/v2/azure-functions/python/tags/list"
_IMAGE_REPO = "mcr.microsoft.com/azure-functions/python"
_CUSTOM_IMAGE = os.getenv("IMAGE_NAME")


@dataclass
class DockerConfigs:
    script_path: Path
    libraries: typing.List = None
    env: typing.Dict = None


class WebHostProxy:

    def __init__(self, proc, addr):
        self._proc = proc
        self._addr = addr

    def request(self, meth, funcname, *args, **kwargs):
        request_method = getattr(requests, meth.lower())
        params = dict(kwargs.pop('params', {}))
        no_prefix = kwargs.pop('no_prefix', False)

        return request_method(
            self._addr + ('/' if no_prefix else '/api/') + funcname,
            *args, params=params, **kwargs)

    def close(self) -> bool:
        """Kill a container by its name. Returns True on success.
        """
        kill_cmd = [_docker_cmd, "rm", "-f", _uuid]
        kill_process = subprocess.run(args=kill_cmd, stdout=subprocess.DEVNULL)
        exit_code = kill_process.returncode

        return exit_code == 0

    def is_healthy(self) -> bool:
        pass


class WebHostDockerContainerBase(unittest.TestCase):

    @staticmethod
    def find_latest_image(image_repo: str,
                          image_url: str) -> str:

        regex = re.compile(_HOST_VERSION + r'.\d+.\d+-python' + _python_version)

        response = requests.get(image_url, allow_redirects=True)
        if not response.ok:
            raise RuntimeError(f'Failed to query latest image for v4'
                               f' Python {_python_version}.'
                               f' Status {response.status_code}')

        tag_list = response.json().get('tags', [])
        # Removing images with a -upgrade and -slim. Upgrade images were
        # temporary images used to onboard customers from a previous version.
        # These images are no longer used.
        tag_list = [x.strip("-upgrade") for x in tag_list]
        tag_list = [x.strip("-slim") for x in tag_list]

        # Listing all the versions from the tags with suffix -python<version>
        python_versions = list(filter(regex.match, tag_list))

        # sorting all the python versions based on the runtime version and
        # getting the latest released runtime version for python.
        latest_version = sorted(python_versions, key=lambda x: float(
            x.split(_HOST_VERSION + '.')[-1].split("-python")[0]))[-1]

        image_tag = f'{image_repo}:{latest_version}'
        return image_tag

    def create_container(self, image_repo: str, image_url: str,
                         configs: DockerConfigs):
        """Create a docker container and record its port. Create a docker
        container according to the image name. Return the port of container.
       """

        worker_path = os.path.join(PROJECT_ROOT, 'azure_functions_worker')
        script_path = os.path.join(TESTS_ROOT, configs.script_path)
        env = {"AzureWebJobsFeatureFlags": "EnableWorkerIndexing",
               "AzureWebJobsStorage": f"{os.getenv('AzureWebJobsStorage')}",
               "AzureWebJobsEventHubConnectionString":
                   f"{os.getenv('AzureWebJobsEventHubConnectionString')}",
               "AzureWebJobsCosmosDBConnectionString":
                   f"{os.getenv('AzureWebJobsCosmosDBConnectionString')}",
               "AzureWebJobsServiceBusConnectionString":
                   f"{os.getenv('AzureWebJobsServiceBusConnectionString')}",
               "AzureWebJobsSqlConnectionString":
                   f"{os.getenv('AzureWebJobsSqlConnectionString')}",
               "AzureWebJobsEventGridTopicUri":
                   f"{os.getenv('AzureWebJobsEventGridTopicUri')}",
               "AzureWebJobsEventGridConnectionKey":
                   f"{os.getenv('AzureWebJobsEventGridConnectionKey')}"
               }

        configs.env.update(env)

        if _CUSTOM_IMAGE:
            image = _CUSTOM_IMAGE
        else:
            image = self.find_latest_image(image_repo, image_url)

        container_worker_path = (
            f"/azure-functions-host/workers/python/{_python_version}/"
            "LINUX/X64/azure_functions_worker"
        )

        function_path = "/home/site/wwwroot"

        if not configs.libraries:
            configs.libraries = ['azurefunctions-extensions-base']
        install_libraries_cmd = []
        install_libraries_cmd.extend(['pip', 'install'])
        install_libraries_cmd.extend(['--platform=manylinux2014_x86_64'])
        install_libraries_cmd.extend(configs.libraries)
        install_libraries_cmd.extend(['-t',
                                        f'{script_path}/{_libraries_path}'])
        install_libraries_cmd.extend(['--only-binary=:all:'])

        install_libraries_process = \
            subprocess.run(args=install_libraries_cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)

        if install_libraries_process.returncode != 0:
            raise RuntimeError('Failed to install libraries')

        run_cmd = []
        run_cmd.extend([_docker_cmd, "run", "-p", "0:80", "-d"])
        run_cmd.extend(["--name", _uuid, "--privileged"])
        run_cmd.extend(["--cap-add", "SYS_ADMIN"])
        run_cmd.extend(["--device", "/dev/fuse"])
        run_cmd.extend(["-e", f"CONTAINER_NAME={_uuid}"])
        run_cmd.extend(["-e", f"AzureFunctionsWebHost__hostid={_uuid}"])
        run_cmd.extend(["-v", f"{worker_path}:{container_worker_path}"])
        run_cmd.extend(["-v", f"{script_path}:{function_path}"])

        if configs.env:
            for key, value in configs.env.items():
                run_cmd.extend(["-e", f"{key}={value}"])

        run_cmd.append(image)
        run_process = subprocess.run(args=run_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)

        if run_process.returncode != 0:
            raise RuntimeError('Failed to create docker container for'
                               f' {image} with uuid {_uuid}.'
                               f' stderr: {run_process.stderr}')

        # Wait for six seconds for the port to expose
        sleep(6)

        # Acquire the port number of the container
        port_cmd = [_docker_cmd, "port", _uuid]
        port_process = subprocess.run(args=port_cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        if port_process.returncode != 0:
            raise RuntimeError(f'Failed to acquire port for {_uuid}.'
                               f' stderr: {port_process.stderr}')
        port_number = port_process.stdout.decode().strip('\n').split(':')[-1]

        # Wait for six seconds for the container to be in ready state
        sleep(6)
        self._addr = f'http://localhost:{port_number}'

        return WebHostProxy(run_process, self._addr)


class WebHostConsumption(WebHostDockerContainerBase):

    def __init__(self, configs: DockerConfigs):
        self.configs = configs

    def spawn_container(self):
        return self.create_container(_MESH_IMAGE_REPO,
                                     _MESH_IMAGE_URL,
                                     self.configs)


class WebHostDedicated(WebHostDockerContainerBase):

    def __init__(self, configs: DockerConfigs):
        self.configs = configs

    def spawn_container(self):
        return self.create_container(_IMAGE_REPO, _IMAGE_URL,
                                     self.configs)
