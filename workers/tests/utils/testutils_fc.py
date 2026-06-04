# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from io import BytesIO
from typing import Dict
from urllib.request import urlopen
from zipfile import ZipFile

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import padding

from ..utils import constants

# Flex Consumption Testing Constants
_DOCKER_PATH = "DOCKER_PATH"
_DOCKER_DEFAULT_PATH = "docker"
_OS_TYPE = "bookworm" if sys.version_info.minor < 14 else "noble"
_MESH_IMAGE_URL = (
    f"https://mcr.microsoft.com/v2/azure-functions/{_OS_TYPE}/"
    "flexconsumption/tags/list"
)
_MESH_IMAGE_REPO = f"mcr.microsoft.com/azure-functions/{_OS_TYPE}/flexconsumption"
_FUNC_GITHUB_ZIP = "https://github.com/Azure/azure-functions-python-library" \
                   "/archive/refs/heads/dev.zip"
_FUNC_FILE_NAME = "azure-functions-python-library-dev"
_CUSTOM_IMAGE = "CUSTOM_IMAGE"
_EXTENSION_BASE_ZIP = 'https://github.com/Azure/azure-functions-python-' \
                      'extensions/archive/refs/heads/dev.zip'


class FlexConsumptionWebHostController:
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
        container.
        """
        url = f'http://localhost:{self._ports[self._uuid]}'

        # Add compulsory fields in specialization context
        env["FUNCTIONS_EXTENSION_VERSION"] = f"~{self._host_version}"
        env["FUNCTIONS_WORKER_RUNTIME"] = "python"
        env["FUNCTIONS_WORKER_RUNTIME_VERSION"] = self._py_version
        env["WEBSITE_SITE_NAME"] = self._uuid
        env["WEBSITE_POD_NAME"] = self._uuid

        # Wait for the container to be ready
        max_retries = 10
        for i in range(max_retries):
            try:
                ping_req = requests.Request(method="GET", url=f"{url}/admin/host/ping")
                ping_response = self.send_request(ping_req)
                if ping_response.ok:
                    break
            except Exception:
                pass
            time.sleep(1)
        else:
            raise RuntimeError(f'Container {self._uuid} did not become ready in time')

        # Flex/Legion host does not download app content during assign (it's a
        # no-op).  In local Docker tests there is no Legion infrastructure, so
        # we must manually mount the content BEFORE the assign call so the
        # host can discover functions when it specializes.
        pkg_name = env.get("SCM_RUN_FROM_PACKAGE") or env.get(
            "WEBSITE_RUN_FROM_PACKAGE"
        )
        if pkg_name:
            local_zip = constants.FUNCTION_APP_ZIPS_DIR / pkg_name
            if not local_zip.exists():
                raise RuntimeError(
                    f"Local function app zip not found: {local_zip}"
                )
            self._mount_package_in_container(str(local_zip))

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

    def _mount_package_in_container(self, local_path: str):
        """Copy a local function app zip into the container and extract it
        at /home/site/wwwroot.

        Flex Consumption is zip-only end-to-end: Core Tools' Flex publish
        path uploads a raw zip via `api/publish`, the Legion platform layer
        mounts that zip's contents onto the worker pod, and the host's
        LegionInstanceManager.ApplyContextAsync is a no-op. The local
        fixtures in `function_app_zips/` are real zip archives.
        """
        with open(local_path, "rb") as f:
            magic = f.read(4)

        if magic[:2] != b'PK':
            raise RuntimeError(
                f"{local_path} is not a zip archive. "
                f"First 4 bytes: {magic!r}"
            )

        container_pkg = "/tmp/app.zip"

        # Copy the zip into the container
        subprocess.run(
            [self._docker_cmd, "cp", local_path,
             f"{self._uuid}:{container_pkg}"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

        # Extract zip using Python's zipfile
        subprocess.run(
            [self._docker_cmd, "exec", self._uuid,
             "python", "-c",
             "import zipfile, os; "
             "os.makedirs('/home/site/wwwroot', exist_ok=True); "
             f"zipfile.ZipFile('{container_pkg}').extractall("
             "'/home/site/wwwroot'); "
             f"os.remove('{container_pkg}')"],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

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

        # For flex consumption, use JWT Bearer token
        jwt_token = self._generate_jwt_token()
        prepped.headers['Authorization'] = f'Bearer {jwt_token}'

        # Add additional headers required by Azure Functions host
        prepped.headers['x-site-deployment-id'] = self._uuid
        prepped.headers['x-ms-client-request-id'] = str(uuid.uuid4())
        prepped.headers['x-ms-request-id'] = str(uuid.uuid4())

        resp = session.send(prepped)
        return resp

    @classmethod
    def _find_latest_mesh_image(
            cls,
            host_major: str,
            python_version: str,
    ) -> str:
        """
        Return the tag for the most recent mesh image that starts with
        <host_major> and ends with “-python<python_version>”.

        Example tag: 4.1040.100-0-python3.13
        """
        if host_major in cls._mesh_images:
            return cls._mesh_images[host_major]

        # <host_major> might already contain dots, so escape it
        tag_pattern = re.compile(
            rf'{re.escape(host_major)}\.\d+\.\d+-\d+-python{python_version}$'
        )

        response = requests.get(_MESH_IMAGE_URL, timeout=10)
        if not response.ok:
            raise RuntimeError(
                f'Failed to query latest image for v{host_major} '
                f'Python {python_version}. '
                f'Status {response.status_code}'
            )

        # Strip “-upgrade” from any temporary tags
        tags = [t.removesuffix("-upgrade") for t in response.json().get("tags", [])]

        # Keep only tags that match host_major and python_version
        candidates = [t for t in tags if tag_pattern.match(t)]
        if not candidates:
            raise RuntimeError(
                f'No mesh image found for v{host_major} Python {python_version}.'
            )

        def _numeric_key(tag: str) -> tuple[int, ...]:
            """
            Convert the part before “-python” to a tuple of integers so that
            numeric comparison works as expected.

            For “4.1040.100-0” we get (4, 1040, 100, 0).
            """
            numeric_part = tag.split("-python")[0].replace("-", ".")
            return tuple(int(piece) for piece in numeric_part.split("."))

        latest_tag = max(candidates, key=_numeric_key)
        image_tag = f"{_MESH_IMAGE_REPO}:{latest_tag}"
        cls._mesh_images[host_major] = image_tag
        return image_tag

    @staticmethod
    def _download_azure_functions() -> str:
        with urlopen(_FUNC_GITHUB_ZIP) as zipresp:
            with ZipFile(BytesIO(zipresp.read())) as zfile:
                zfile.extractall(tempfile.gettempdir())

    @staticmethod
    def _download_extensions() -> str:
        folder = tempfile.gettempdir()
        with urlopen(_EXTENSION_BASE_ZIP) as zipresp:
            with ZipFile(BytesIO(zipresp.read())) as zfile:
                zfile.extractall(tempfile.gettempdir())

        return folder

    def spawn_container(self,
                        image: str,
                        env: Dict[str, str] = {}) -> int:
        """Create a docker container and record its port."""
        worker_name = 'azure_functions_worker' \
            if sys.version_info.minor < 13 else 'proxy_worker'

        worker_path = os.path.join(constants.WORKERS_ROOT, worker_name)
        container_worker_path = (
            f"/azure-functions-host/workers/python/{self._py_version}/"
            f"LINUX/X64/{worker_name}"
        )

        # For Python 3.13+, also mount the runtime libraries
        runtime_v2_path = None
        runtime_v1_path = None
        container_runtime_v2_path = None
        container_runtime_v1_path = None

        if sys.version_info.minor >= 13:
            repo_root = constants.REPO_ROOT
            runtime_v2_path = os.path.join(
                repo_root, 'runtimes', 'v2', 'azure_functions_runtime'
            )
            runtime_v1_path = os.path.join(
                repo_root, 'runtimes', 'v1', 'azure_functions_runtime_v1'
            )
            container_runtime_v2_path = (
                f"/azure-functions-host/workers/python/{self._py_version}/"
                "LINUX/X64/azure_functions_runtime"
            )
            container_runtime_v1_path = (
                f"/azure-functions-host/workers/python/{self._py_version}/"
                "LINUX/X64/azure_functions_runtime_v1"
            )

        ext_folder = self._download_extensions()

        base_ext_container_path = (
            f"/azure-functions-host/workers/python/{self._py_version}/"
            "LINUX/X64/azurefunctions/extensions/base"
        )

        base_ext_local_path = (
            f'{ext_folder}/azure-functions-python'
            '-extensions-dev/azurefunctions-extensions-base'
            '/azurefunctions/extensions/base'
        )

        # Get paths to google.protobuf and grpcio packages to mount them
        # This ensures the container uses the same protobuf/grpc versions
        # as the host, which is critical when protobuf files are generated
        # with v5.x but the container has v4.x.
        protobuf_path = None
        grpc_path = None
        container_protobuf_path = None
        container_grpc_path = None
        # Only mount the host's grpc/protobuf into the Linux mesh container
        # when the host itself is Linux. Windows/macOS hosts ship the
        # compiled extensions for their own platform (e.g. cygrpc.*.pyd on
        # Windows), and bind-mounting them into the container produces:
        #   ImportError: cannot import name 'cygrpc' from 'grpc._cython'
        # On non-Linux hosts we fall back to the grpc/protobuf bundled in
        # the mesh image.
        if sys.platform.startswith("linux"):
            try:
                import google.protobuf
                import grpc
                protobuf_path = os.path.dirname(google.protobuf.__file__)
                grpc_path = os.path.dirname(grpc.__file__)

                # Container paths for protobuf and grpcio
                container_protobuf_path = (
                    f"/azure-functions-host/workers/python/{self._py_version}/"
                    "LINUX/X64/google/protobuf"
                )
                container_grpc_path = (
                    f"/azure-functions-host/workers/python/{self._py_version}/"
                    "LINUX/X64/grpc"
                )
            except ImportError:
                protobuf_path = None
                grpc_path = None

        run_cmd = []
        run_cmd.extend([self._docker_cmd, "run", "-p", "0:80", "-d"])
        run_cmd.extend(["--name", self._uuid])
        run_cmd.extend(["-e", f"CONTAINER_NAME={self._uuid}"])
        encryption_key = os.getenv('_DUMMY_CONT_KEY')
        full_key_bytes = base64.b64decode(encryption_key.encode())
        aes_key_bytes = full_key_bytes[:32]
        aes_key_base64 = base64.b64encode(aes_key_bytes).decode()
        run_cmd.extend(["-e", f"CONTAINER_ENCRYPTION_KEY={aes_key_base64}"])
        run_cmd.extend(["-e", "WEBSITE_PLACEHOLDER_MODE=1"])
        run_cmd.extend(["-e", f"WEBSITE_SITE_NAME={self._uuid}"])
        run_cmd.extend(["-e", f"WEBSITE_POD_NAME={self._uuid}"])
        run_cmd.extend(["-e", "WEBSITE_SKU=FlexConsumption"])
        # Mount Worker Code
        run_cmd.extend(["-v", f'{worker_path}:{container_worker_path}'])

        # Mount runtime libraries for Python 3.13+
        if runtime_v2_path and runtime_v1_path:
            run_cmd.extend([
                "-v", f'{runtime_v2_path}:{container_runtime_v2_path}'
            ])
            run_cmd.extend([
                "-v", f'{runtime_v1_path}:{container_runtime_v1_path}'
            ])

        run_cmd.extend(["-v",
                        f'{base_ext_local_path}:{base_ext_container_path}'])

        # Mount protobuf and grpcio packages if they were found
        if protobuf_path:
            run_cmd.extend(["-v", f'{protobuf_path}:{container_protobuf_path}'])
        if grpc_path:
            run_cmd.extend(["-v", f'{grpc_path}:{container_grpc_path}'])

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
        time.sleep(6)
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
        """Get SWT token for site-restricted authentication."""
        exp_ns = int((time.time() + 24 * 60 * 60) * 1000000000)
        token = cls._encrypt_context(os.getenv('_DUMMY_CONT_KEY'), f'exp={exp_ns}')
        return token

    def _generate_jwt_token(self) -> str:
        """Generate JWT token for Flex consumption authentication."""
        try:
            import jwt
        except ImportError as e:
            raise RuntimeError(
                "PyJWT library required. Install with: pip install pyjwt"
            ) from e

        exp_time = int(time.time()) + (24 * 60 * 60)
        iat_time = int(time.time())
        site_name = self._uuid
        issuer = f"https://{site_name}.azurewebsites.net"

        payload = {
            'exp': exp_time,
            'iat': iat_time,
            'nbf': iat_time,
            'iss': issuer,
            'aud': site_name,
            'sub': site_name,
        }

        encryption_key_str = os.getenv('_DUMMY_CONT_KEY')
        if not encryption_key_str:
            raise RuntimeError("_DUMMY_CONT_KEY environment variable not set")

        key_bytes = base64.b64decode(encryption_key_str.encode())
        key = key_bytes[:32]
        jwt_token = jwt.encode(payload, key, algorithm='HS256')
        return jwt_token

    @classmethod
    def _get_site_encrypted_context(cls, site_name: str, env: Dict[str, str]) -> str:
        """Get encrypted specialization context."""
        env["WEBSITE_SITE_NAME"] = site_name
        ctx = {"SiteId": 1, "SiteName": site_name, "Environment": env}
        json_ctx = json.dumps(ctx)
        encrypted = cls._encrypt_context(os.getenv('_DUMMY_CONT_KEY'), json_ctx)
        return encrypted

    @classmethod
    def _encrypt_context(cls, encryption_key: str, plain_text: str) -> str:
        """Encrypt context for specialization."""
        encryption_key_bytes = base64.b64decode(encryption_key.encode())
        aes_key = encryption_key_bytes[:32]

        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        plain_text_bytes = padder.update(plain_text.encode()) + padder.finalize()

        iv_bytes = '0123456789abcedf'.encode()
        cipher = Cipher(
            algorithms.AES(aes_key),
            modes.CBC(iv_bytes),
            backend=default_backend(),
        )
        encryptor = cipher.encryptor()
        encrypted_bytes = encryptor.update(plain_text_bytes) + encryptor.finalize()

        iv_base64 = base64.b64encode(iv_bytes).decode()
        encrypted_base64 = base64.b64encode(encrypted_bytes).decode()

        digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
        digest.update(aes_key)
        key_sha256 = digest.finalize()
        key_sha256_base64 = base64.b64encode(key_sha256).decode()

        return f'{iv_base64}.{encrypted_base64}.{key_sha256_base64}'

    def __enter__(self):
        mesh_image = (os.environ.get(_CUSTOM_IMAGE)
                      or self._find_latest_mesh_image(self._host_version,
                                                      self._py_version))
        self.spawn_container(image=mesh_image)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        logs = self.get_container_logs()
        self.safe_kill_container()
        shutil.rmtree(os.path.join(tempfile.gettempdir(), _FUNC_FILE_NAME),
                      ignore_errors=True)

        if traceback:
            print(f'Test failed with container logs: {logs}',
                  file=sys.stderr,
                  flush=True)
