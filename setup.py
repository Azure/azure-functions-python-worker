import distutils.cmd
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import json
import tempfile
import urllib.request
import zipfile
import re
from distutils import dir_util
from distutils.command import build

from setuptools import setup
from setuptools.command import develop

from azure_functions_worker import __version__

# The GitHub repository of the Azure Functions Host
WEBHOST_GITHUB_API = "https://api.github.com/repos/Azure/azure-functions-host"
WEBHOST_TAG_PREFIX = "v3."

# Extensions necessary for non-core bindings.
AZURE_EXTENSIONS = """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netcoreapp3.1</TargetFramework>
    <AzureFunctionsVersion>v3</AzureFunctionsVersion>
    <WarningsAsErrors></WarningsAsErrors>
    <DefaultItemExcludes>**</DefaultItemExcludes>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference
        Include="Microsoft.NET.Sdk.Functions"
        Version="3.0.3"
    />
    <PackageReference
        Include="Microsoft.Azure.WebJobs.Extensions.CosmosDB"
        Version="3.0.5"
    />
    <PackageReference
        Include="Microsoft.Azure.WebJobs.Extensions.EventHubs"
        Version="3.0.6"
    />
    <PackageReference
        Include="Microsoft.Azure.WebJobs.Extensions.EventGrid"
        Version="2.1.0"
    />
    <PackageReference
        Include="Microsoft.Azure.WebJobs.Extensions.Storage"
        Version="3.0.10"
    />
    <PackageReference
        Include="Microsoft.Azure.WebJobs.ServiceBus"
        Version="3.0.0-beta8"
    />
  </ItemGroup>
</Project>
"""


NUGET_CONFIG = """\
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="nuget.org" value="https://www.nuget.org/api/v2/" />
    <add key="azure_app_service"
         value="https://www.myget.org/F/azure-appservice/api/v2" />
    <add key="azure_app_service_staging"
         value="https://www.myget.org/F/azure-appservice-staging/api/v2" />
    <add key="buildTools"
         value="https://www.myget.org/F/30de4ee06dd54956a82013fa17a3accb/" />
    <add key="AspNetVNext"
         value="https://www.myget.org/F/aspnetcore-dev/api/v3/index.json" />
  </packageSources>
</configuration>
"""


class BuildGRPC:
    """Generate gRPC bindings."""
    def _gen_grpc(self):
        root = pathlib.Path(os.path.abspath(os.path.dirname(__file__)))

        proto_root_dir = root / 'azure_functions_worker' / 'protos'
        proto_src_dir = proto_root_dir / '_src' / 'src' / 'proto'
        build_dir = root / 'build'
        staging_root_dir = build_dir / 'protos'
        staging_dir = (staging_root_dir
                       / 'azure_functions_worker' / 'protos')
        built_protos_dir = build_dir / 'built_protos'

        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        shutil.copytree(proto_src_dir, staging_dir)

        os.makedirs(built_protos_dir)

        protos = [
            os.sep.join(('shared', 'NullableTypes.proto')),
            os.sep.join(('identity', 'ClaimsIdentityRpc.proto')),
            'FunctionRpc.proto'
        ]

        for proto in protos:
            subprocess.run([
                sys.executable, '-m', 'grpc_tools.protoc',
                '-I', os.sep.join(('azure_functions_worker', 'protos')),
                '--python_out', str(built_protos_dir),
                '--grpc_python_out', str(built_protos_dir),
                os.sep.join(('azure_functions_worker', 'protos', proto)),
            ], check=True, stdout=sys.stdout, stderr=sys.stderr,
                cwd=staging_root_dir)

        compiled_files = glob.glob(
            str(built_protos_dir / '**' / '*.py'),
            recursive=True)

        if not compiled_files:
            print('grpc_tools.protoc produced no Python files',
                  file=sys.stderr)
            sys.exit(1)

        # Needed to support absolute imports in files. See
        # https://github.com/protocolbuffers/protobuf/issues/1491
        self.make_absolute_imports(compiled_files)

        dir_util.copy_tree(built_protos_dir, str(proto_root_dir))

    def make_absolute_imports(self, compiled_files):
        for compiled in compiled_files:
            with open(compiled, 'r+') as f:
                content = f.read()
                f.seek(0)
                # Convert lines of the form:
                # import xxx_pb2 as xxx__pb2 to
                # from azure_functions_worker.protos import xxx_pb2 as..
                p1 = re.sub(
                    r'\nimport (.*?_pb2)',
                    r'\nfrom azure_functions_worker.protos import \g<1>',
                    content)
                # Convert lines of the form:
                # from identity import xxx_pb2 as.. to
                # from azure_functions_worker.protos.identity import xxx_pb2..
                p2 = re.sub(
                    r'from ([a-z]*) (import.*_pb2)',
                    r'from azure_functions_worker.protos.\g<1> \g<2>',
                    p1)
                f.write(p2)
                f.truncate()


class build(build.build, BuildGRPC):
    def run(self, *args, **kwargs):
        self._gen_grpc()
        super().run(*args, **kwargs)


class develop(develop.develop, BuildGRPC):
    def run(self, *args, **kwargs):
        self._gen_grpc()
        super().run(*args, **kwargs)


class extension(distutils.cmd.Command):
    description = (
        'Resolve WebJobs Extensions from AZURE_EXTENSIONS and NUGET_CONFIG.'
    )
    user_options = [
        ('extensions-dir', None,
         'A path to the directory where extension should be installed')
    ]

    def initialize_options(self):
        self.extensions_dir = None

    def finalize_options(self):
        if self.extensions_dir is None:
            self.extensions_dir = \
                pathlib.Path(__file__).parent / 'build' / 'extensions'

    def _install_extensions(self):
        if not self.extensions_dir.exists():
            os.makedirs(self.extensions_dir, exist_ok=True)

        if not (self.extensions_dir / 'host.json').exists():
            with open(self.extensions_dir / 'host.json', 'w') as f:
                print('{}', file=f)

        if not (self.extensions_dir / 'extensions.csproj').exists():
            with open(self.extensions_dir / 'extensions.csproj', 'w') as f:
                print(AZURE_EXTENSIONS, file=f)

        with open(self.extensions_dir / 'NuGet.config', 'w') as f:
            print(NUGET_CONFIG, file=f)

        env = os.environ.copy()
        env['TERM'] = 'xterm'  # ncurses 6.1 workaround
        try:
            subprocess.run(
                args=['dotnet', 'build', '-o', '.'], check=True,
                cwd=str(self.extensions_dir),
                stdout=sys.stdout, stderr=sys.stderr, env=env)
        except Exception:
            print(".NET Core SDK is required to build the extensions. "
                  "Please visit https://aka.ms/dotnet-download")
            sys.exit(1)

    def run(self):
        self._install_extensions()


class webhost(distutils.cmd.Command):
    description = 'Download and setup Azure Functions Web Host.'
    user_options = [
        ('webhost-version', None,
            'A Functions Host version to be downloaded (e.g. 3.0.15278).'),
        ('webhost-dir', None,
            'A path to the directory where Azure Web Host will be installed.'),
    ]

    def initialize_options(self):
        self.webhost_version = None
        self.webhost_dir = None

    def finalize_options(self):
        if self.webhost_version is None:
            self.webhost_version = self._get_webhost_version()

        if self.webhost_dir is None:
            self.webhost_dir = \
                pathlib.Path(__file__).parent / 'build' / 'webhost'

    def _get_webhost_version(self) -> str:
        # Return the latest matched version (e.g. 3.0.15278)
        github_api_url = f'{WEBHOST_GITHUB_API}/tags?page=1&per_page=10'
        print(f'Checking latest webhost version from {github_api_url}')
        github_response = urllib.request.urlopen(github_api_url)
        tags = json.loads(github_response.read())

        # As tags are placed in time desending order, the latest v3
        # tag should be the first occurance starts with 'v3.' string
        latest_v3 = [
            gt for gt in tags if gt['name'].startswith(WEBHOST_TAG_PREFIX)
        ]
        return latest_v3[0]['name'].replace('v', '')

    def _download_webhost_zip(self, version: str) -> str:
        # Return the path of the downloaded host
        temporary_file = tempfile.NamedTemporaryFile()
        zip_url = (
            'https://github.com/Azure/azure-functions-host/archive/'
            f'v{version}.zip'
        )
        print(f'Downloading Functions Host ({version}) from {zip_url}')

        with temporary_file as zipf:
            zipf.close()
            try:
                urllib.request.urlretrieve(zip_url, zipf.name)
            except Exception as e:
                print('Failed to download Functions Host source code from'
                      f' {zip_url}: {e!r}', file=sys.stderr)
                sys.exit(1)

        print(f'Functions Host is downloaded into {temporary_file.name}')
        return temporary_file.name

    def _create_webhost_folder(self, dest_folder: pathlib.Path):
        if dest_folder.exists():
            shutil.rmtree(dest_folder)
        os.makedirs(dest_folder, exist_ok=True)
        print(f'Functions Host folder is created in {dest_folder}')

    def _extract_webhost_zip(self, version: str, src_zip: str, dest: str):
        print(f'Extracting Functions Host from {src_zip}')

        with zipfile.ZipFile(src_zip) as archive:
            # We cannot simply use extractall(), as the archive
            # contains Windows-style path names, which are not
            # automatically converted into Unix-style paths, so
            # extractall() will produce a flat directory with
            # backslashes in file names.

            for archive_name in archive.namelist():
                prefix = f'azure-functions-host-{version}/'
                if archive_name.startswith(prefix):
                    sanitized_name = archive_name \
                        .replace('\\', os.sep) \
                        .replace(prefix, '')
                    dest_filename = dest / sanitized_name
                    zipinfo = archive.getinfo(archive_name)

                    try:
                        if not dest_filename.parent.exists():
                            os.makedirs(dest_filename.parent, exist_ok=True)

                        if zipinfo.is_dir():
                            os.makedirs(dest_filename, exist_ok=True)
                        else:
                            with archive.open(archive_name) as src, \
                                    open(dest_filename, 'wb') as dst:
                                dst.write(src.read())
                    except Exception as e:
                        print(f'Failed to extract file {archive_name}'
                              f': {e!r}', file=sys.stderr)
                        sys.exit(1)

        print(f'Functions Host is extracted into {dest}')

    def _chmod_protobuf_generation_script(self, webhost_dir: pathlib.Path):
        # This script is needed to set to executable in order to build the
        # WebJobs.Script.Grpc project in Linux and MacOS
        script_path = (
            webhost_dir / 'src' / 'WebJobs.Script.Grpc' / 'generate_protos.sh'
        )
        if sys.platform != 'win32' and os.path.exists(script_path):
            print('Change generate_protos.sh script permission')
            os.chmod(script_path, 0o555)

    def _compile_webhost(self, webhost_dir: pathlib.Path):
        print(f'Compiling Functions Host from {webhost_dir}')

        try:
            subprocess.run(
                args=['dotnet', 'build', 'WebJobs.Script.sln', '-o', 'bin'],
                check=True,
                cwd=str(webhost_dir),
                stdout=sys.stdout, stderr=sys.stderr)
        except Exception:
            print(f"Failed to compile webhost in {webhost_dir}. "
                  ".NET Core SDK is required to build the solution. "
                  "Please visit https://aka.ms/dotnet-download",
                  file=sys.stderr)
            sys.exit(1)

        print('Functions Host is compiled successfully')

    def run(self):
        # Prepare webhost
        zip_path = self._download_webhost_zip(self.webhost_version)
        self._create_webhost_folder(self.webhost_dir)
        self._extract_webhost_zip(version=self.webhost_version,
                                  src_zip=zip_path,
                                  dest=self.webhost_dir)
        self._chmod_protobuf_generation_script(self.webhost_dir)
        self._compile_webhost(self.webhost_dir)


with open("README.md") as readme:
    long_description = readme.read()


setup(
    name='azure-functions-worker',
    version=__version__,
    description='Python Language Worker for Azure Functions Host',
    author="Microsoft Corp.",
    author_email="azurefunctions@microsoft.com",
    keywords="azure azurefunctions python",
    url="https://github.com/Azure/azure-functions-python-worker",
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: Web Environment',
    ],
    license='MIT',
    packages=['azure_functions_worker',
              'azure_functions_worker.protos',
              'azure_functions_worker.protos.identity',
              'azure_functions_worker.protos.shared',
              'azure_functions_worker.bindings',
              'azure_functions_worker.bindings.shared_memory_data_transfer',
              'azure_functions_worker.utils',
              'azure_functions_worker._thirdparty'],
    install_requires=[
        'grpcio~=1.33.2',
        'grpcio-tools~=1.33.2',
    ],
    extras_require={
        'dev': [
            'azure-functions==1.7.2',
            'azure-eventhub~=5.1.0',
            'python-dateutil~=2.8.1',
            'flake8~=3.7.9',
            'mypy',
            'pytest',
            'requests==2.*',
            'coverage',
            'pytest-sugar',
            'pytest-cov',
            'pytest-xdist',
            'pytest-randomly',
            'pytest-instafail',
            'pytest-rerunfailures',
            'ptvsd'
        ]
    },
    include_package_data=True,
    cmdclass={
        'develop': develop,
        'build': build,
        'webhost': webhost,
        'extension': extension
    },
    test_suite='tests'
)
