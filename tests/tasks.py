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
from distutils import dir_util

import requests
from invoke import task

from utils.constants import EXTENSIONS_CSPROJ_TEMPLATE, NUGET_CONFIG

ROOT = pathlib.Path(os.path.abspath(os.path.dirname(__file__))).parent
BUILD_DIR = ROOT / "build"
WEBHOST_GITHUB_API = "https://api.github.com/repos/Azure/azure-functions-host"
WEBHOST_TAG_PREFIX = "v4."
WEBHOST_GIT_REPO = "https://github.com/Azure/azure-functions-host/archive"


def make_absolute_imports(compiled_files):
    for compiled in compiled_files:
        with open(compiled, "r+") as f:
            content = f.read()
            f.seek(0)
            # Convert lines of the form:
            # import xxx_pb2 as xxx__pb2 to
            # from azure_functions_worker.protos import xxx_pb2 as..
            p1 = re.sub(
                r"\nimport (.*?_pb2)",
                r"\nfrom azure_functions_worker.protos import \g<1>",
                content,
            )
            # Convert lines of the form:
            # from identity import xxx_pb2 as.. to
            # from azure_functions_worker.protos.identity import xxx_pb2..
            p2 = re.sub(
                r"from ([a-z]*) (import.*_pb2)",
                r"from azure_functions_worker.protos.\g<1> \g<2>",
                p1,
            )
            f.write(p2)
            f.truncate()


@task
def build(c, clean=False):
    """Builds the gRPC files."""

    if clean:
        print("Cleaning gRPC files...")
        shutil.rmtree(BUILD_DIR / "built_protos")
        shutil.rmtree(BUILD_DIR / "protos")
    else:
        print("Building gRPC files...")
        proto_root_dir = ROOT / "azure_functions_worker" / "protos"
        proto_src_dir = proto_root_dir / "_src" / "src" / "proto"
        staging_root_dir = BUILD_DIR / "protos"
        staging_dir = staging_root_dir / "azure_functions_worker" / "protos"
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
                    os.sep.join(("azure_functions_worker", "protos")),
                    "--python_out",
                    str(built_protos_dir),
                    "--grpc_python_out",
                    str(built_protos_dir),
                    os.sep.join(("azure_functions_worker", "protos", proto)),
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
            print("grpc_tools.protoc produced no Python files",
                  file=sys.stderr)
            sys.exit(1)

        # Needed to support absolute imports in files. See
        # https://github.com/protocolbuffers/protobuf/issues/1491
        make_absolute_imports(compiled_files)

        dir_util.copy_tree(str(built_protos_dir), str(proto_root_dir))


def get_webhost_version():
    github_api_url = f"{WEBHOST_GITHUB_API}/tags?page=1&per_page=10"
    print(f"Checking latest webhost version from {github_api_url}")
    response = requests.get(github_api_url)
    response.raise_for_status()
    tags = response.json()
    latest = next(gt for gt in tags if gt["name"].startswith(WEBHOST_TAG_PREFIX))
    return latest["name"].replace("v", "")


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
            print(f"Failed to download Functions Host source code from {zip_url}: {e}", file=sys.stderr)
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
                sanitized_name = archive_name.replace("\\", os.sep).replace(prefix, "")
                dest_filename = dest / sanitized_name
                zipinfo = archive.getinfo(archive_name)
                if not dest_filename.parent.exists():
                    os.makedirs(dest_filename.parent, exist_ok=True)
                if zipinfo.is_dir():
                    os.makedirs(dest_filename, exist_ok=True)
                else:
                    with archive.open(archive_name) as src, open(dest_filename, "wb") as dst:
                        dst.write(src.read())
    print(f"Functions Host is extracted into {dest}")


def chmod_protobuf_generation_script(webhost_dir):
    script_path = webhost_dir / "src" / "WebJobs.Script.Grpc" / "generate_protos.sh"
    if sys.platform != "win32" and script_path.exists():
        print("Change generate_protos.sh script permission")
        os.chmod(script_path, 0o555)


def compile_webhost(webhost_dir):
    print(f"Compiling Functions Host from {webhost_dir}")
    try:
        subprocess.run(
            ["dotnet", "build", "WebJobs.Script.sln", "-o", "bin", "/p:TreatWarningsAsErrors=false"],
            check=True,
            cwd=str(webhost_dir),
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except subprocess.CalledProcessError:
        print(
            f"Failed to compile webhost in {webhost_dir}. "
            ".NET Core SDK is required to build the solution. "
            "Please visit https://aka.ms/dotnet-download",
            file=sys.stderr,
        )
        sys.exit(1)
    print("Functions Host is compiled successfully")


@task
def webhost(c, clean=False,  webhost_version=None, webhost_dir=None,
            branch_name=None):
    """Builds the webhost ."""

    if clean:
        print("Cleaning Webhost build files...")
        shutil.rmtree(BUILD_DIR / "built_protos")

    if webhost_version is None:
        webhost_version = get_webhost_version()

    if webhost_dir is None:
        webhost_dir = pathlib.Path(__file__).parent / "build" / "webhost"
    else:
        webhost_dir = pathlib.Path(webhost_dir)

    zip_path = download_webhost_zip(webhost_version, branch_name)
    create_webhost_folder(webhost_dir)
    version = branch_name or webhost_version
    extract_webhost_zip(version.replace("/", "-"), zip_path, webhost_dir)
    chmod_protobuf_generation_script(webhost_dir)
    compile_webhost(webhost_dir)


@task
def extensions(c, clean=False):
    """Builds the extensions."""

    if clean:
        print("Cleaning extension files...")
        shutil.rmtree(BUILD_DIR / "extensions")
    else:
        print("Installing extensions...")
        extensions_dir = BUILD_DIR / "extensions"
        if not extensions_dir.exists():
            os.makedirs(extensions_dir, exist_ok=True)

        if not (extensions_dir / "host.json").exists():
            with open(extensions_dir / "host.json", "w") as f:
                print("{}", file=f)

        if not (extensions_dir / "extensions.csproj").exists():
            with open(extensions_dir / "extensions.csproj", "w") as f:
                print(EXTENSIONS_CSPROJ_TEMPLATE, file=f)

        with open(extensions_dir / "NuGet.config", "w") as f:
            print(NUGET_CONFIG, file=f)

        env = os.environ.copy()
        env["TERM"] = "xterm"  # ncurses 6.1 workaround
        try:
            subprocess.run(
                args=["dotnet", "build", "-o", "."],
                check=True,
                cwd=str(extensions_dir),
                stdout=sys.stdout,
                stderr=sys.stderr,
                env=env,
            )
        except Exception:  # NoQA
            print(
                ".NET Core SDK is required to build the extensions. "
                "Please visit https://aka.ms/dotnet-download"
            )
            sys.exit(1)


@task
def clean_builds(c):
    """Cleans the builds."""

    shutil.rmtree(BUILD_DIR)
