# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Package a Python Linux x64 worker stage with checked-out runtime sources."""

import argparse
import ast
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parents[3]
VERSION_FILE = ROOT / "workers" / "proxy_worker" / "version.py"
PACKAGE_NAME = "azure-functions-python-worker"
MANIFEST_NAME = "worker-manifest.json"
REQUIRED_FILES = (
    "worker.py",
    "proxy_worker/version.py",
    "proxy_worker/protos/FunctionRpc_pb2.py",
    "proxy_worker/protos/FunctionRpc_pb2_grpc.py",
    "six.py",
)
REQUIRED_DIRECTORIES = (
    "azure",
    "azure_functions_runtime",
    "azure_functions_runtime_v1",
    "azurefunctions",
    "google",
    "grpc",
    "markupsafe",
    "uvloop",
    "werkzeug",
)
R2P2_REQUIRED_FILES = (
    "r2p2",
    "worker.py",
    "bridge/bridge.py",
    "bridge/protos_adapter.py",
    "azure_functions_runtime/native_invocation.py",
    "azure_functions_runtime/utils/executor.py",
    "azure_functions_runtime_v1/native_invocation.py",
    "azure_functions_runtime_v1/utils/executor.py",
)
R2P2_REQUIRED_DIRECTORIES = (
    "azure",
    "azurefunctions",
    "azure_functions_runtime",
    "azure_functions_runtime_v1",
)
R2P2_FORBIDDEN = ("azure_functions_worker", "grpc", "proxy_worker", "uvloop")


def read_version(version_file: Path) -> str:
    try:
        module = ast.parse(version_file.read_text(encoding="utf-8"))
    except SyntaxError as error:
        raise ValueError(f"Invalid version file: {version_file}") from error
    versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "VERSION"
                for target in node.targets)
    ]
    if (len(versions) != 1 or not isinstance(versions[0], str)
            or not re.fullmatch(
                r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?",
                versions[0])):
        raise ValueError(
            f"Expected one literal version string in {version_file}")
    return versions[0]


def validate_payload(source: Path, version: str,
                     python_version: str = "3.14") -> list[Path]:
    if not re.fullmatch(r"[1-9][0-9]*\.[0-9]+", python_version):
        raise ValueError(f"Expected a Python major.minor version: {python_version}")
    is_r2p2 = tuple(map(int, python_version.split("."))) >= (3, 15)
    required_files = R2P2_REQUIRED_FILES if is_r2p2 else REQUIRED_FILES
    required_directories = (R2P2_REQUIRED_DIRECTORIES if is_r2p2
                            else REQUIRED_DIRECTORIES)
    missing = [
        name for name in required_files if not (source / name).is_file()
    ] + [
        name for name in required_directories if not (source / name).is_dir()
    ]
    if missing:
        raise ValueError(
            "Missing staged worker contents: " + ", ".join(missing))
    if (not is_r2p2
            and read_version(source / "proxy_worker" / "version.py") != version):
        raise ValueError(
            "Staged proxy worker version does not match version.py")
    if is_r2p2:
        forbidden = [name for name in R2P2_FORBIDDEN
                     if (source / name).exists()]
        if forbidden:
            raise ValueError(
                "Forbidden R2P2 staged contents: " + ", ".join(forbidden))
    if (source / MANIFEST_NAME).exists():
        raise ValueError(f"Staging directory already contains {MANIFEST_NAME}")

    members = sorted(source.rglob("*"))
    for path in members:
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError(f"Unsupported staged file type: {path}")

    abi = python_version.replace(".", "")
    if not is_r2p2:
        for directory, module in (
            ("grpc/_cython", "cygrpc"), ("uvloop", "loop"),
        ):
            name = f"{module}.cpython-{abi}-x86_64-linux-gnu.so"
            if not (source / directory / name).is_file():
                raise ValueError(
                    f"Missing Python {python_version} Linux x64 extension: "
                    f"{directory}/{name}")

    for path in members:
        if not path.is_file():
            continue
        if path.suffix.lower() in (".pyd", ".dll", ".dylib"):
            raise ValueError(f"Expected a Linux x64 native library: {path}")
        is_binary = is_r2p2 and path == source / "r2p2"
        if ".so" in path.suffixes or is_binary:
            tag = re.search(r"\.(?:cpython-|cp)(\d+)([^.]*)", path.name)
            if tag and (
                tag.group(1) != abi
                or tag.group(0) != f".cpython-{abi}-x86_64-linux-gnu"
            ):
                raise ValueError(
                    f"Expected Python {python_version} Linux x64 ABI: {path}")
            with path.open("rb") as native_file:
                header = native_file.read(20)
            if (len(header) != 20 or header[:6] != b"\x7fELF\x02\x01"
                    or int.from_bytes(header[18:20], "little") != 62):
                raise ValueError(
                    f"Expected a Linux x64 ELF native file: {path}")
            if is_binary and int.from_bytes(header[16:18], "little") not in (
                2, 3,
            ):
                raise ValueError(f"Expected an ELF executable: {path}")

    return [
        path for path in members
        if path.relative_to(source).as_posix() not in (
            ".artifactignore", "LICENSE")
        and "__pycache__" not in path.relative_to(source).parts
        and path.suffix not in (".pyc", ".pyo")
    ]


def build_package(source: Path, output: Path,
                  version_file: Path = VERSION_FILE,
                  python_version: str = "3.14") -> tuple[Path, Path]:
    source = source.resolve()
    output = output.resolve()
    if not source.is_dir():
        raise ValueError(f"Staged worker directory does not exist: {source}")
    if output.is_relative_to(source):
        raise ValueError(
            "Output directory must be outside the staging directory")

    with tempfile.TemporaryDirectory() as temporary:
        staged = Path(temporary) / "worker"
        shutil.copytree(source, staged, symlinks=True)
        for directory, package in (
            ("v1", "azure_functions_runtime_v1"),
            ("v2", "azure_functions_runtime"),
        ):
            target = staged / package
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(ROOT / "runtimes" / directory / package, target,
                            symlinks=True)
        return _build_staged_package(
            staged, output, version_file, python_version)


def _build_staged_package(source: Path, output: Path, version_file: Path,
                          python_version: str) -> tuple[Path, Path]:
    version = read_version(version_file)
    members = validate_payload(source, version, python_version)
    manifest = {
        "name": PACKAGE_NAME,
        "version": version,
        "python_version": python_version,
        "platform": "linux-x64",
        "entrypoint": "worker.py",
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    abi = python_version.replace(".", "")
    filename = f"{PACKAGE_NAME}-py{abi}-linux-x64.tar.gz"
    archive_path = output / filename
    checksum_path = output / f"{filename}.sha256"
    archive_entries = [
        (path, path.relative_to(source).as_posix()) for path in members
    ]
    archive_entries.append((ROOT / "LICENSE", "LICENSE"))
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output) as temporary:
        temporary_archive = Path(temporary) / filename
        with temporary_archive.open("wb") as archive_file:
            with gzip.GzipFile(filename="", mode="wb", fileobj=archive_file,
                               mtime=0) as compressed:
                with tarfile.open(fileobj=compressed, mode="w") as archive:
                    for path, name in archive_entries:
                        info = archive.gettarinfo(str(path), arcname=name)
                        info.uid = info.gid = 0
                        info.uname = info.gname = ""
                        info.mtime = 0
                        info.mode = (0o755 if info.isdir()
                                     or name == "r2p2"
                                     or info.mode & 0o111 else 0o644)
                        if info.isfile():
                            with path.open("rb") as payload_file:
                                archive.addfile(info, payload_file)
                        else:
                            archive.addfile(info)
                    info = tarfile.TarInfo(MANIFEST_NAME)
                    info.size = len(manifest_bytes)
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(manifest_bytes))

        with temporary_archive.open("rb") as archive_file:
            digest = hashlib.file_digest(archive_file, "sha256").hexdigest()
        temporary_checksum = Path(temporary) / checksum_path.name
        temporary_checksum.write_text(
            f"{digest}  {filename}\n", encoding="ascii", newline="\n")
        temporary_archive.replace(archive_path)
        temporary_checksum.replace(checksum_path)
    return archive_path, checksum_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True,
                        help="Existing flat Linux x64 staging directory")
    parser.add_argument("--output", type=Path, required=True,
                        help="Directory for the archive and SHA-256 file")
    parser.add_argument("--python-version", default="3.14",
                        help="Target Python major.minor version (default: 3.14)")
    args = parser.parse_args()
    try:
        archive, checksum = build_package(
            args.source, args.output, python_version=args.python_version)
    except (OSError, ValueError, SyntaxError, tarfile.TarError) as error:
        parser.exit(1, f"Worker packaging failed: {error}\n")
    print(f"Worker archive: {archive}")
    print(f"SHA-256 file: {checksum}")


if __name__ == "__main__":
    main()
