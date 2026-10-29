# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Validate staged legacy (3.10-3.12), proxy (3.13-3.14), or R2P2 (3.15+) payloads.

Structural and native-binary checks work on cross-build hosts. --check-imports
additionally requires matching target Python/OS/architecture with -I -S, and
checks legacy/proxy imports and launcher startup without a Functions host.
R2P2 validation checks layout, pruned packages and executable architecture;
its embedded Python/bridge startup requires separate native integration tests.
"""

import argparse
import importlib
import os
import platform
import re
import struct
import subprocess
import sys
from pathlib import Path


PROTO_MODULES = (
    "FunctionRpc_pb2",
    "FunctionRpc_pb2_grpc",
    "identity.ClaimsIdentityRpc_pb2",
    "identity.ClaimsIdentityRpc_pb2_grpc",
    "shared.NullableTypes_pb2",
    "shared.NullableTypes_pb2_grpc",
)
RUNTIMES = ("azure_functions_runtime", "azure_functions_runtime_v1")
FORBIDDEN_R2P2 = ("azure_functions_worker", "proxy_worker", "grpc", "uvloop")


def parse_python_version(value):
    match = re.match(r"^(\d+)\.(\d+)(?:\D|$)", value)
    if match is None:
        raise ValueError(f"Invalid Python version: {value}")
    version = tuple(map(int, match.groups()))
    if version[0] != 3 or version < (3, 10):
        raise ValueError(f"Unsupported Python version: {value}")
    return version


def worker_package(version):
    if version >= (3, 15):
        return "r2p2"
    return "azure_functions_worker" if version < (3, 13) else "proxy_worker"


def expected_contents(version, os_name):
    """Return file and directory manifests, keeping type checks explicit."""
    package = worker_package(version)
    files = ["worker.py"]
    directories = ["azure", "azurefunctions"]
    if package == "r2p2":
        files.extend([
            "r2p2.exe" if os_name == "WINDOWS" else "r2p2",
            "bridge/bridge.py", "bridge/protos_adapter.py",
        ])
        for runtime in RUNTIMES:
            directories.append(runtime)
            files.extend([f"{runtime}/native_invocation.py",
                          f"{runtime}/utils/executor.py"])
        return files, directories

    files.extend([".artifactignore", "six.py"])
    directories.extend(["google", "grpc", "markupsafe", "werkzeug", package,
                        f"{package}/protos/_src"])
    entry = "main" if package == "azure_functions_worker" else "start_worker"
    files.extend(f"{package}/{name}.py" for name in (
        "__init__", "__main__", entry, "dispatcher", "utils/dependency",
        "protos/__init__",
    ))
    files.extend(f"{package}/protos/{name.replace('.', '/')}.py"
                 for name in PROTO_MODULES)
    if package == "azure_functions_worker":
        directories.append("dateutil")
        files.append(f"{package}/_vendored/google/protobuf/__init__.py")
    else:
        directories.extend(RUNTIMES)
    return files, directories


def validate_binary(path, os_name, architecture):
    """Inspect PE, ELF and thin/universal Mach-O without executing target code."""
    data = path.read_bytes()
    if os_name == "WINDOWS":
        if len(data) < 64 or data[:2] != b"MZ":
            raise RuntimeError(f"{path.name} is not a PE executable")
        offset = struct.unpack_from("<I", data, 0x3c)[0]
        if offset + 6 > len(data) or data[offset:offset + 4] != b"PE\0\0":
            raise RuntimeError(f"{path.name} has an invalid PE header")
        actual = struct.unpack_from("<H", data, offset + 4)[0]
        expected = {"x86": 0x014c, "x64": 0x8664, "arm64": 0xaa64}[architecture]
        machines = {actual}
    elif os_name == "LINUX":
        if len(data) < 20 or data[:4] != b"\x7fELF" or data[5] != 1:
            raise RuntimeError(f"{path.name} is not a little-endian ELF executable")
        expected = {"x86": 3, "x64": 62, "arm64": 183}[architecture]
        machines = {struct.unpack_from("<H", data, 18)[0]}
    else:
        expected = {"x86": 7, "x64": 0x01000007, "arm64": 0x0100000c}[architecture]
        thin = {b"\xce\xfa\xed\xfe": "<", b"\xcf\xfa\xed\xfe": "<",
                b"\xfe\xed\xfa\xce": ">", b"\xfe\xed\xfa\xcf": ">"}
        fat = {b"\xca\xfe\xba\xbe": (">", 20), b"\xbe\xba\xfe\xca": ("<", 20),
               b"\xca\xfe\xba\xbf": (">", 32), b"\xbf\xba\xfe\xca": ("<", 32)}
        magic = data[:4]
        if magic in thin and len(data) >= 8:
            machines = {struct.unpack_from(thin[magic] + "I", data, 4)[0]}
        elif magic in fat and len(data) >= 8:
            endian, stride = fat[magic]
            count = struct.unpack_from(endian + "I", data, 4)[0]
            if not count or 8 + count * stride > len(data):
                raise RuntimeError(f"{path.name} has an invalid Mach-O fat header")
            machines = {struct.unpack_from(endian + "I", data, 8 + i * stride)[0]
                        for i in range(count)}
        else:
            raise RuntimeError(f"{path.name} is not a Mach-O executable")
    if expected not in machines:
        raise RuntimeError(f"{path.name} does not target {os_name} {architecture}; "
                           f"found machine types {sorted(machines)}")


def validate_contents(root, version, os_name, architecture, grpc_build=None):
    root = Path(root).resolve()
    files, directories = expected_contents(version, os_name)
    missing = [name for name in files if not (root / name).is_file()]
    missing.extend(name + "/" for name in directories if not (root / name).is_dir())
    if missing:
        raise RuntimeError("Missing worker payload files/folders: "
                           + ", ".join(missing))
    if worker_package(version) == "r2p2":
        present = [name for name in FORBIDDEN_R2P2 if (root / name).exists()]
        if present:
            raise RuntimeError("Pruned packages unexpectedly present: "
                               + ", ".join(present))
        binary = "r2p2.exe" if os_name == "WINDOWS" else "r2p2"
        validate_binary(root / binary, os_name, architecture)
    else:
        if not grpc_build:
            raise ValueError("--grpc-build is required for legacy/proxy payloads")
        # Windows cp3xx and Unix cpython-3xx extension tags, including RC ABIs.
        pattern = f"*{version[0]}{version[1]}*-{grpc_build}"
        if not any(path.is_file() for path in (root / "grpc/_cython").glob(pattern)):
            raise RuntimeError(f"Missing gRPC binary: grpc/_cython/{pattern}")
    print(f"Validated {worker_package(version)} contents for {os_name} {architecture}",
          flush=True)


def validate_interpreter(version, os_name, architecture):
    if sys.version_info[:2] != version:
        raise RuntimeError("Validation interpreter does not match target Python")
    actual_os = {"win32": "WINDOWS", "linux": "LINUX", "darwin": "OSX"}.get(
        sys.platform)
    machine = platform.machine().lower()
    # A 32-bit Windows Python can report the 64-bit OS machine architecture.
    actual_arch = ("x86" if struct.calcsize("P") == 4 else
                   {"amd64": "x64", "x86_64": "x64", "arm64": "arm64",
                    "aarch64": "arm64"}.get(machine))
    if (actual_os, actual_arch) != (os_name, architecture):
        raise RuntimeError("Import validation requires matching target "
                   "OS/architecture; "
                           f"expected {os_name}/{architecture}, "
                           f"found {actual_os}/{actual_arch}")


def validate_imports(root, package):
    if package == "r2p2":
        raise ValueError("R2P2 embedded-runtime startup requires "
                         "native integration tests")
    if not sys.flags.isolated or not sys.flags.no_site:
        raise RuntimeError("Payload validation requires Python -I -S")
    root = Path(root).resolve()
    sys.path.insert(0, str(root))
    entry = "main" if package == "azure_functions_worker" else "start_worker"
    modules = ["grpc", "grpc._cython.cygrpc", "google.protobuf", "azure.functions",
               f"{package}.{entry}", f"{package}.dispatcher"]
    modules.extend(f"{package}.protos.{name}" for name in PROTO_MODULES)
    for name in modules:
        module = importlib.import_module(name)
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise RuntimeError(f"{name} was imported from outside the artifact")
        print(f"Imported {name} from {module.__file__}", flush=True)
    env = os.environ.copy()
    for name in ("CONTAINER_NAME", "WEBSITE_INSTANCE_ID"):
        env.pop(name, None)
    subprocess.run(
        [sys.executable, "-I", "-S", str(root / "worker.py"), "--help"],
        cwd=root, env=env, check=True, timeout=60,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--python-version", required=True)
    parser.add_argument("--os", dest="os_name", choices=("WINDOWS", "LINUX", "OSX"),
                        required=True)
    parser.add_argument("--architecture", choices=("x64", "x86", "arm64"),
                        required=True)
    parser.add_argument("--grpc-build")
    parser.add_argument("--check-imports", action="store_true")
    args = parser.parse_args()
    version = parse_python_version(args.python_version)
    validate_contents(args.root, version, args.os_name, args.architecture,
                      args.grpc_build)
    if args.check_imports:
        validate_interpreter(version, args.os_name, args.architecture)
        validate_imports(args.root, worker_package(version))


if __name__ == "__main__":
    main()