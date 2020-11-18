import distutils.cmd
import glob
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import re
from distutils import dir_util
from distutils.command import build

from setuptools import setup
from setuptools.command import develop


# TODO: Change this to something more stable when available.
# TODO: Change this to use 3.x
WEBHOST_URL = (
    "https://github.com/Azure/azure-functions-host/releases/download"
    "/v2.0.14494/Functions.Binaries.2.0.14494.no-runtime.zip"
)

# Extensions necessary for non-core bindings.
AZURE_EXTENSIONS = """\
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>netstandard2.0</TargetFramework>
    <WarningsAsErrors></WarningsAsErrors>
    <DefaultItemExcludes>**</DefaultItemExcludes>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference
        Include="Microsoft.Azure.WebJobs.Script.ExtensionsMetadataGenerator"
        Version="1.1.7"
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
         value="https://dotnet.myget.org/F/aspnetcore-dev/api/v3/index.json" />
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


class webhost(distutils.cmd.Command):
    description = 'Download and setup Azure Functions Web Host.'
    user_options = [
        ('webhost-url', None,
            'A custom URL to download Azure Web Host from.'),
        ('webhost-dir', None,
            'A path to the directory where Azure Web Host will be installed.'),
    ]

    def initialize_options(self):
        self.webhost_url = None
        self.webhost_dir = None
        self.extensions_dir = None

    def finalize_options(self):
        if self.webhost_url is None:
            self.webhost_url = WEBHOST_URL

        if self.webhost_dir is None:
            self.webhost_dir = \
                pathlib.Path(__file__).parent / 'build' / 'webhost'

        if self.extensions_dir is None:
            self.extensions_dir = \
                pathlib.Path(__file__).parent / 'build' / 'extensions'

    def _install_webhost(self):
        with tempfile.NamedTemporaryFile() as zipf:
            zipf.close()
            try:
                print('Downloading Azure Functions Web Host...')
                urllib.request.urlretrieve(self.webhost_url, zipf.name)
            except Exception as e:
                print(f"could not download Azure Functions Web Host binaries "
                      f"from {self.webhost_url}: {e!r}", file=sys.stderr)
                sys.exit(1)

            if not self.webhost_dir.exists():
                os.makedirs(self.webhost_dir, exist_ok=True)

            with zipfile.ZipFile(zipf.name) as archive:
                print('Extracting Azure Functions Web Host binaries...')

                # We cannot simply use extractall(), as the archive
                # contains Windows-style path names, which are not
                # automatically converted into Unix-style paths, so
                # extractall() will produce a flat directory with
                # backslashes in file names.
                for archive_name in archive.namelist():
                    destination = \
                        self.webhost_dir / archive_name.replace('\\', os.sep)
                    if not destination.parent.exists():
                        os.makedirs(destination.parent, exist_ok=True)
                    with archive.open(archive_name) as src, \
                            open(destination, 'wb') as dst:
                        dst.write(src.read())

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
                args=['dotnet', 'build', '-o', 'bin'], check=True,
                cwd=str(self.extensions_dir),
                stdout=sys.stdout, stderr=sys.stderr, env=env)
        except Exception:
            print(f"dotnet core SDK is required")
            sys.exit(1)

    def run(self):
        self._install_webhost()
        self._install_extensions()


with open("README.md") as readme:
    long_description = readme.read()


setup(
    name='azure-functions-worker',
    version='1.1.8',
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
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
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
              'azure_functions_worker.utils',
              'azure_functions_worker._thirdparty'],
    install_requires=[
        'grpcio~=1.33.1',
        'grpcio-tools~=1.33.1',
    ],
    extras_require={
        'dev': [
            'azure-functions==1.5.0',
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
            'pytest-rerunfailures'
        ]
    },
    include_package_data=True,
    cmdclass={
        'build': build,
        'develop': develop,
        'webhost': webhost,
    },
    test_suite='tests'
)
