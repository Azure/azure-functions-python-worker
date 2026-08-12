# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Usage:
This file defines tasks for building Protos, webhost and extensions

To use these tasks, you can run the following commands:

1. Build protos:
   invoke -c test_setup build-protos

2. Set up the Azure Functions Web Host:
   invoke -c test_setup webhost

3. Install WebJobs extensions:
   invoke -c test_setup extensions
"""

import glob
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from invoke import task

from utils.constants import EXTENSIONS_CSPROJ_TEMPLATE

ROOT_DIR = pathlib.Path(__file__).parent.parent
BUILD_DIR = ROOT_DIR / 'build'
NUGET_CONFIG_PATH = ROOT_DIR.parent / 'nuget.config'
WEBHOST_GITHUB_API = "https://api.github.com/repos/Azure/azure-functions-host"
WEBHOST_GIT_REPO = "https://github.com/Azure/azure-functions-host/archive"
WEBHOST_TAG_PREFIX = "v4."
WORKER_DIR = "azure_functions_worker" if sys.version_info.minor < 13 else "proxy_worker"
# The worker's generated protobuf stubs continue to import top-level
# ``google.protobuf``. ``azure_functions_worker/__init__.py`` decides at
# package-import time whether to redirect those imports to the vendored
# copy (via ``sys.modules`` aliases) based on whether the customer ships
# their own protobuf. Build-time rewriting of the stubs is no longer
# needed, so this flag stays False.
REWRITE_PROTOBUF = False


def get_webhost_version() -> str:
    # Return the latest matched version (e.g. 4.39.1)
    github_api_url = f"{WEBHOST_GITHUB_API}/tags?page=1&per_page=10"
    print(f"Checking latest webhost version from {github_api_url}")
    github_response = urllib.request.urlopen(github_api_url)
    tags = json.loads(github_response.read())

    # As tags are placed in time desending order, the latest v3
    # tag should be the first occurance starts with 'v3.' string
    latest = [gt for gt in tags if gt["name"].startswith(WEBHOST_TAG_PREFIX)]
    return latest[0]["name"].replace("v", "")


def download_webhost_zip(version, branch):
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        if branch:
            zip_url = f"{WEBHOST_GIT_REPO}/refs/heads/{branch}.zip"
        else:
            zip_url = f"{WEBHOST_GIT_REPO}/v{version}.zip"

        print(f"Downloading Functions Host from {zip_url}")
        try:
            urllib.request.urlretrieve(zip_url, temp_file.name)
        except Exception as e:
            print(
                f"Failed to download Functions Host source code from {zip_url}: {e}",
                file=sys.stderr)
            sys.exit(1)
        return temp_file.name


def create_webhost_folder(dest_folder):
    if dest_folder.exists():
        shutil.rmtree(dest_folder)
    os.makedirs(dest_folder, exist_ok=True)
    print(f"Functions Host folder is created in {dest_folder}")


def extract_webhost_zip(version, src_zip, dest):
    print(f"Extracting Functions Host from {src_zip}")
    with zipfile.ZipFile(src_zip, 'r') as archive:
        for archive_name in archive.namelist():
            prefix = f"azure-functions-host-{version}/"
            if archive_name.startswith(prefix):
                sanitized_name = archive_name.replace("\\", os.sep).replace(
                    prefix, "")
                dest_filename = dest / sanitized_name
                zipinfo = archive.getinfo(archive_name)
                if not dest_filename.parent.exists():
                    os.makedirs(dest_filename.parent, exist_ok=True)
                if zipinfo.is_dir():
                    os.makedirs(dest_filename, exist_ok=True)
                else:
                    with archive.open(archive_name) as src, open(dest_filename,
                                                                 "wb") as dst:
                        dst.write(src.read())
    print(f"Functions Host is extracted into {dest}")


def chmod_protobuf_generation_script(webhost_dir):
    script_path = webhost_dir / "src" / "WebJobs.Script.Grpc" / "generate_protos.sh"
    if sys.platform != "win32" and script_path.exists():
        print("Change generate_protos.sh script permission")
        os.chmod(script_path, 0o555)


def compile_webhost(webhost_dir):
    print(f"Compiling Functions Host from {webhost_dir}")
    # Build only the WebHost project (and its dependencies) instead of the
    # entire WebJobs.Script.sln. The solution also contains test projects,
    # benchmarks and isolated-worker samples that the tests never run; building
    # them is slow, consumes far more disk, and pulls many extra NuGet packages
    # that can fail to restore on the internal CI feed. The WebHost project
    # output already contains the full runtime dependency closure needed to run
    # the host.
    webhost_project = (pathlib.Path("src") / "WebJobs.Script.WebHost"
                       / "WebJobs.Script.WebHost.csproj")
    try:
        subprocess.run(
            [
                "dotnet", "build", str(webhost_project),
                "/m:1",  # Disable parallel MSBuild
                "/nodeReuse:false",  # Prevent MSBuild node reuse
                f"--property:OutputPath={webhost_dir}/bin",  # Set output folder
                "/p:TreatWarningsAsErrors=false"
            ],
            check=True,
            cwd=str(webhost_dir),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError:
        print(
            f"Failed to compile webhost in {webhost_dir}. "
            "A compatible .NET Core SDK is required to build the solution. "
            "Please visit https://aka.ms/dotnet-download",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Functions Host is compiled successfully")


def gen_grpc():
    proto_root_dir = ROOT_DIR / WORKER_DIR / "protos"
    proto_src_dir = proto_root_dir / "_src" / "src" / "proto"
    staging_root_dir = BUILD_DIR / "protos"
    staging_dir = staging_root_dir / WORKER_DIR / "protos"
    built_protos_dir = BUILD_DIR / "built_protos"

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    shutil.copytree(proto_src_dir, staging_dir)
    os.makedirs(built_protos_dir)

    protos = [
        os.sep.join(("shared", "NullableTypes.proto")),
        os.sep.join(("identity", "ClaimsIdentityRpc.proto")),
        "FunctionRpc.proto",
    ]

    for proto in protos:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "grpc_tools.protoc",
                "-I",
                os.sep.join((WORKER_DIR, "protos")),
                "--python_out",
                str(built_protos_dir),
                "--grpc_python_out",
                str(built_protos_dir),
                os.sep.join((WORKER_DIR, "protos", proto)),
            ],
            check=True,
            stdout=sys.stdout,
            stderr=sys.stderr,
            cwd=staging_root_dir,
        )

    compiled_files = glob.glob(
        str(built_protos_dir / "**" / "*.py"), recursive=True
    )

    if not compiled_files:
        print("grpc_tools.protoc produced no Python files", file=sys.stderr)
        sys.exit(1)

    # Needed to support absolute imports in files. See
    # https://github.com/protocolbuffers/protobuf/issues/1491
    make_absolute_imports(compiled_files)
    copy_tree_merge(str(built_protos_dir), str(proto_root_dir))


def copy_tree_merge(src, dst):
    """
    Recursively copy all files and subdirectories from src to dst,
    overwriting files if they already exist. This emulates what
    distutils.dir_util.copy_tree did without removing existing directories.
    """
    if not os.path.exists(dst):
        os.makedirs(dst)

    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)

        if os.path.isdir(s):
            copy_tree_merge(s, d)
        else:
            shutil.copy2(s, d)


def make_absolute_imports(compiled_files):
    vendored_protobuf = (
        f"{WORKER_DIR}._vendored.google.protobuf"
    )

    for compiled in compiled_files:
        with open(compiled, "r+") as f:
            content = f.read()
            f.seek(0)
            # Convert lines of the form:
            # import xxx_pb2 as xxx__pb2 to
            # from azure_functions_worker.protos import xxx_pb2 as..
            p1 = re.sub(
                r"\nimport (.*?_pb2)",
                fr"\nfrom {WORKER_DIR}.protos import \g<1>",
                content,
            )
            # Convert lines of the form:
            # from identity import xxx_pb2 as.. to
            # from azure_functions_worker.protos.identity import xxx_pb2..
            p2 = re.sub(
                r"from ([a-z]*) (import.*_pb2)",
                fr"from {WORKER_DIR}.protos.\g<1> \g<2>",
                p1,
            )

            if REWRITE_PROTOBUF:
                # Redirect every `from google.protobuf[...] import ...`
                # statement to the vendored copy. Anchored at line start
                # (after a newline or at file start) so we don't touch
                # string literals or comments.
                p2 = re.sub(
                    r"(?m)^from google\.protobuf"
                    r"(?P<tail>(?:\.[A-Za-z0-9_.]+)?\s+import\b)",
                    fr"from {vendored_protobuf}\g<tail>",
                    p2,
                )
                # Redirect `import google.protobuf[.X]` statements. The
                # generated stubs only emit the `from ...` form today,
                # but be defensive in case future protoc output changes.
                p2 = re.sub(
                    r"(?m)^import google\.protobuf"
                    r"(?P<sub>\.[A-Za-z0-9_.]+)?"
                    r"(?P<asname>\s+as\s+[A-Za-z_][A-Za-z0-9_]*)?$",
                    lambda m: (
                        f"import {vendored_protobuf}"
                        f"{m.group('sub') or ''}"
                        f"{m.group('asname') or ' as google_protobuf'}"
                    ),
                    p2,
                )

            f.write(p2)
            f.truncate()


def install_extensions(extensions_dir):
    if not extensions_dir.exists():
        os.makedirs(extensions_dir, exist_ok=True)

    if not (extensions_dir / "host.json").exists():
        with open(extensions_dir / "host.json", "w") as f:
            f.write("{}")

    if not (extensions_dir / "extensions.csproj").exists():
        with open(extensions_dir / "extensions.csproj", "w") as f:
            f.write(EXTENSIONS_CSPROJ_TEMPLATE)

    nuget_config_path = extensions_dir / "NuGet.config"
    shutil.copy2(NUGET_CONFIG_PATH, nuget_config_path)

    env = os.environ.copy()
    env["TERM"] = "xterm"  # ncurses 6.1 workaround
    try:
        subprocess.run(
            args=[
                "dotnet", "build", "-o", ".",
                f"--property:RestoreConfigFile={nuget_config_path}",
            ],
            check=True,
            cwd=str(extensions_dir),
            stdout=sys.stdout,
            stderr=sys.stderr,
            env=env,
        )
    except subprocess.CalledProcessError:
        print(
            ".NET Core SDK is required to build the extensions. "
            "Please visit https://aka.ms/dotnet-download"
        )
        sys.exit(1)


@task
def extensions(c, clean=False, extensions_dir=None):
    """Build extensions."""
    extensions_dir = extensions_dir or BUILD_DIR / "extensions"
    if clean:
        print(f"Deleting Extensions Directory: {extensions_dir}")
        shutil.rmtree(extensions_dir, ignore_errors=True)
        print("Deleted Extensions Directory")
        return

    print("Installing Extensions")
    install_extensions(extensions_dir)
    print("Extensions installed successfully.")


@task
def vendor_deps(c, target=None):
    """Vendor third-party deps into azure_functions_worker._vendored.

    Copies the currently-installed ``google.protobuf`` package into
    ``azure_functions_worker/_vendored/google/protobuf/`` (pure-Python
    only — native extensions are skipped) and rewrites its internal
    imports so the vendored copy is fully self-contained. The worker
    only uses the vendored copy when the customer ships their own
    ``google.protobuf``; otherwise the worker uses the protobuf install
    on its own ``sys.path``. The decision is made at runtime in
    ``azure_functions_worker/__init__.py``.

    Safe to re-run; the script is idempotent.

    Skipped for the proxy worker (Python >= 3.13) which has its own
    dependency isolation and is unaffected by the protobuf shadowing issue.
    """
    if WORKER_DIR != "azure_functions_worker":
        print(
            f"Skipping vendor_deps for {WORKER_DIR} "
            "(only required for the azure_functions_worker)."
        )
        return

    # ROOT_DIR is the `workers/` directory (see top of file), so its parent
    # is the repository root.
    repo_root = ROOT_DIR.parent
    script = repo_root / "eng" / "scripts" / "vendor_deps.py"
    if not script.exists():
        raise RuntimeError(
            f"vendor_deps.py not found at {script}. "
            "Expected it in eng/scripts/."
        )

    default_target = (
        ROOT_DIR / "azure_functions_worker" / "_vendored"
    )
    target_path = pathlib.Path(target) if target else default_target

    print(f"Vendoring google.protobuf into {target_path} ...")
    try:
        subprocess.check_call([
            sys.executable, str(script),
            "--target", str(target_path),
            "--package", "google.protobuf",
        ])
    except subprocess.CalledProcessError as ex:
        raise RuntimeError(
            "vendor_deps.py failed. Ensure 'protobuf' is installed in the "
            "current environment (pip install -e workers/[dev])."
        ) from ex
    print("Vendoring complete.")


@task
def build_protos(c, clean=False):
    """Build gRPC bindings."""

    if clean:
        shutil.rmtree(BUILD_DIR / 'protos')
        return
    # Populate azure_functions_worker/_vendored/ before generating stubs.
    # make_absolute_imports rewrites the generated *_pb2.py files to import
    # from the vendored google.protobuf, so the vendored tree must exist
    # before anything imports the freshly generated stubs.
    vendor_deps(c)
    print("Generating gRPC bindings...")
    gen_grpc()
    print("gRPC bindings generated successfully.")


@task
def webhost(c, clean=False, webhost_version=None, webhost_dir=None,
            branch_name=None):
    """Builds the webhost"""

    if webhost_dir is None:
        webhost_dir = BUILD_DIR / "webhost"
    else:
        webhost_dir = pathlib.Path(webhost_dir)

    if clean:
        print("Deleting webhost dir")
        shutil.rmtree(webhost_dir, ignore_errors=True)
        print("Deleted webhost dir")
        return

    if webhost_version is None:
        webhost_version = get_webhost_version()

    zip_path = download_webhost_zip(webhost_version, branch_name)
    create_webhost_folder(webhost_dir)
    version = branch_name or webhost_version
    extract_webhost_zip(version.replace("/", "-"), zip_path, webhost_dir)
    chmod_protobuf_generation_script(webhost_dir)
    compile_webhost(webhost_dir)


@task
def clean(c):
    """Clean build directory."""

    print("Deleting build directory")
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    print("Deleted build directory")
