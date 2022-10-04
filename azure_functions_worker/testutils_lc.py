# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import Dict

import base64
import json
import os
import re
import subprocess
import sys
import time
import uuid

from Crypto.Cipher import AES
from Crypto.Hash.SHA256 import SHA256Hash
from Crypto.Util.Padding import pad
import requests

# Linux Consumption Testing Constants
_DOCKER_PATH = "DOCKER_PATH"
_DOCKER_DEFAULT_PATH = "docker"
_MESH_IMAGE_URL = "https://mcr.microsoft.com/v2/azure-functions/mesh/tags/list"
_MESH_IMAGE_REPO = "mcr.microsoft.com/azure-functions/mesh"
_DUMMY_CONT_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


class LinuxConsumptionWebHostController:
    """A controller for spawning mesh Docker container and apply multiple
    test cases on it.
    """

    _docker_cmd = os.getenv(_DOCKER_PATH, _DOCKER_DEFAULT_PATH)
    _ports: Dict[str, str] = {}  # { uuid: port }
    _mesh_images: Dict[str, str] = {}  # { host version: image tag }

    def __init__(self, host_version: str, python_version: str):
        """Initialize a new container for
        """
        self._uuid = str(uuid.uuid4())
        self._host_version = host_version  # "3"
        self._py_version = python_version  # "3.9"

    @property
    def url(self) -> str:
        if self._uuid not in self._ports:
            raise RuntimeError(f'Failed to assign container {self._name} since'
                               ' it is not spawned')

        return f'http://localhost:{self._ports[self._uuid]}'

    def assign_container(self, env: Dict[str, str] = {}):
        """Make a POST request to /admin/instance/assign to specialize the
        container
        """
        url = f'http://localhost:{self._ports[self._uuid]}'

        # Add compulsory fields in specialization context
        env["FUNCTIONS_EXTENSION_VERSION"] = f"~{self._host_version}"
        env["FUNCTIONS_WORKER_RUNTIME"] = "python"
        env["FUNCTIONS_WORKER_RUNTIME_VERSION"] = self._py_version
        env["WEBSITE_SITE_NAME"] = self._uuid
        env["WEBSITE_HOSTNAME"] = f"{self._uuid}.azurewebsites.com"

        # Send the specialization context via a POST request
        req = requests.Request(
            method="POST",
            url=f"{url}/admin/instance/assign",
            data=json.dumps({
                "encryptedContext": self._get_site_encrypted_context(
                    self._uuid, env
                )
            })
        )
        response = self.send_request(req)
        if not response.ok:
            stdout = self.get_container_logs()
            raise RuntimeError(f'Failed to specialize container {self._uuid}'
                               f' at {url} (status {response.status_code}).'
                               f' stdout: {stdout}')

    def send_request(
        self,
        req: requests.Request,
        ses: requests.Session = None
    ) -> requests.Response:
        """Send a request with authorization token. Return a Response object"""
        session = ses
        if session is None:
            session = requests.Session()

        prepped = session.prepare_request(req)
        prepped.headers['Content-Type'] = 'application/json'
        prepped.headers['x-ms-site-restricted-token'] = (
            self._get_site_restricted_token()
        )
        prepped.headers['x-site-deployment-id'] = self._uuid

        resp = session.send(prepped)
        return resp

    @classmethod
    def _find_latest_mesh_image(cls,
                                host_major: str,
                                python_version: str) -> str:
        """Find the latest image in https://mcr.microsoft.com/v2/
        azure-functions/mesh/tags/list. Match either (3.1.3, or 3.1.3-python3.x)
        """
        if host_major in cls._mesh_images:
            return cls._mesh_images[host_major]

        # match 3.1.3
        regex = re.compile(host_major + r'.\d+.\d+')

        # match 3.1.3-python3.x
        if python_version != '3.6':
            regex = re.compile(host_major + r'.\d+.\d+-python' + python_version)

        response = requests.get(_MESH_IMAGE_URL, allow_redirects=True)
        if not response.ok:
            raise RuntimeError(f'Failed to query latest image for v{host_major}'
                               f' Python {python_version}.'
                               f' Status {response.status_code}')

        tag_list = response.json().get('tags', [])
        version = list(filter(regex.match, tag_list))[-1]

        image_tag = f'{_MESH_IMAGE_REPO}:{version}'
        cls._mesh_images[host_major] = image_tag
        return image_tag

    def spawn_container(self,
                        image: str,
                        env: Dict[str, str] = {}) -> int:
        """Create a docker container and record its port. Create a docker
        container according to the image name. Return the port of container.
        """
        # Construct environment variables and start the docker container
        worker_path = os.path.dirname(__file__)
        container_worker_path = (
            f"/azure-functions-host/workers/python/{self._py_version}/"
            "LINUX/X64/azure_functions_worker"
        )

        run_cmd = []
        run_cmd.extend([self._docker_cmd, "run", "-p", "0:80", "-d"])
        run_cmd.extend(["--name", self._uuid, "--privileged"])
        run_cmd.extend(["--cap-add", "SYS_ADMIN"])
        run_cmd.extend(["--device", "/dev/fuse"])
        run_cmd.extend(["-e", f"CONTAINER_NAME={self._uuid}"])
        run_cmd.extend(["-e", f"CONTAINER_ENCRYPTION_KEY={_DUMMY_CONT_KEY}"])
        run_cmd.extend(["-e", "WEBSITE_PLACEHOLDER_MODE=1"])
        run_cmd.extend(["-v", f'{worker_path}:{container_worker_path}'])

        for key, value in env.items():
            run_cmd.extend(["-e", f"{key}={value}"])
        run_cmd.append(image)

        run_process = subprocess.run(args=run_cmd,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        if run_process.returncode != 0:
            raise RuntimeError('Failed to spawn docker container for'
                               f' {image} with uuid {self._uuid}.'
                               f' stderr: {run_process.stderr}')

        # Wait for three seconds for the port to expose
        time.sleep(3)

        # Acquire the port number of the container
        port_cmd = [self._docker_cmd, "port", self._uuid]
        port_process = subprocess.run(args=port_cmd,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        if port_process.returncode != 0:
            raise RuntimeError(f'Failed to acquire port for {self._uuid}.'
                               f' stderr: {port_process.stderr}')
        port_number = port_process.stdout.decode().strip('\n').split(':')[-1]

        # Register port number onto the table
        self._ports[self._uuid] = port_number

        # Wait for three seconds for the container to be in ready state
        time.sleep(3)
        return port_number

    def get_container_logs(self) -> str:
        """Get container logs, the first element in tuple is stdout and the
        second element is stderr
        """
        get_logs_cmd = [self._docker_cmd, "logs", self._uuid]
        get_logs_process = subprocess.run(args=get_logs_cmd,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)

        # The `docker logs` command will merge stdout and stderr into stdout
        return get_logs_process.stdout.decode('utf-8')

    def safe_kill_container(self) -> bool:
        """Kill a container by its name. Returns True on success.
        """
        kill_cmd = [self._docker_cmd, "rm", "-f", self._uuid]
        kill_process = subprocess.run(args=kill_cmd, stdout=subprocess.DEVNULL)
        exit_code = kill_process.returncode

        if self._uuid in self._ports:
            del self._ports[self._uuid]
        return exit_code == 0

    @classmethod
    def _get_site_restricted_token(cls) -> str:
        """Get the header value which can be used by x-ms-site-restricted-token
        which expires in one day.
        """
        exp_ns = int(time.time() + 24 * 60 * 60) * 1000000000
        return cls._encrypt_context(_DUMMY_CONT_KEY, f'exp={exp_ns}')

    @classmethod
    def _get_site_encrypted_context(cls,
                                    site_name: str,
                                    env: Dict[str, str]) -> str:
        """Get the encrypted context for placeholder mode specialization"""
        ctx = {
            "SiteId": 1,
            "SiteName": site_name,
            "Environment": env
        }

        # Ensure WEBSITE_SITE_NAME is set to simulate production mode
        ctx["Environment"]["WEBSITE_SITE_NAME"] = site_name
        return cls._encrypt_context(_DUMMY_CONT_KEY, json.dumps(ctx))

    @classmethod
    def _encrypt_context(cls, encryption_key: str, plain_text: str) -> str:
        """Encrypt plain text context into a encrypted message which can
        be accepted by the host
        """
        encryption_key_bytes = base64.b64decode(encryption_key.encode())
        plain_text_bytes = pad(plain_text.encode(), 16)
        iv_bytes = '0123456789abcedf'.encode()

        # Start encryption
        cipher = AES.new(encryption_key_bytes, AES.MODE_CBC, iv=iv_bytes)
        encrypted_bytes = cipher.encrypt(plain_text_bytes)

        # Prepare final result
        iv_base64 = base64.b64encode(iv_bytes).decode()
        encrypted_base64 = base64.b64encode(encrypted_bytes).decode()
        key_sha256 = SHA256Hash(encryption_key_bytes).digest()
        key_sha256_base64 = base64.b64encode(key_sha256).decode()
        return f'{iv_base64}.{encrypted_base64}.{key_sha256_base64}'

    def __enter__(self):
        mesh_image = self._find_latest_mesh_image(self._host_version,
                                                  self._py_version)
        self.spawn_container(image=mesh_image)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logs = self.get_container_logs()
        self.safe_kill_container()

        if traceback:
            print(f'Test failed with container logs: {logs}',
                  file=sys.stderr,
                  flush=True)
