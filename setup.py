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
from distutils.command import build

from setuptools import setup
from setuptools.command import develop


# TODO: change this to something more stable when available.
WEBHOST_URL = ('https://ci.appveyor.com/api/buildjobs/sfelyng3x6p5sus0'
               '/artifacts'
               '/Functions.Binaries.2.0.12642.no-runtime.zip')

# Extensions necessary for non-core bindings.
AZURE_EXTENSIONS = [
    {
        "id": "Microsoft.Azure.WebJobs.Script.ExtensionsMetadataGenerator",
        "version": "1.0.1"
    },
    {
        "id": "Microsoft.Azure.WebJobs.Extensions.CosmosDB",
        "version": "3.0.1"
    },
    {
        "id": "Microsoft.Azure.WebJobs.Extensions.EventHubs",
        "version": "3.0.0"
    },
    {
        "id": "Microsoft.Azure.WebJobs.Extensions.EventGrid",
        "version": "2.0.0"
    },
    {
        "id": "Microsoft.Azure.WebJobs.Extensions.Storage",
        "version": "3.0.0"
    },
    {
        "id": "Microsoft.Azure.WebJobs.ServiceBus",
        "version": "3.0.0-beta8"
    },
]


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
        staging_root_dir = root / 'build' / 'protos'
        staging_dir = (staging_root_dir
                       / 'azure_functions_worker' / 'protos')
        build_dir = staging_dir / 'azure_functions_worker' / 'protos'
        built_protos_dir = root / 'build' / 'built_protos'
        built_proto_files_dir = (built_protos_dir
                                 / 'azure_functions_worker' / 'protos')

        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

        if os.path.exists(built_protos_dir):
            shutil.rmtree(built_protos_dir)

        proto_files = glob.glob(str(proto_src_dir / '**' / '*.proto'),
                                recursive=True)

        os.makedirs(build_dir)
        for proto_file in proto_files:
            shutil.copy(proto_file, build_dir)

        protos = [os.path.basename(proto_file) for proto_file in proto_files]

        full_protos = []
        for proto in protos:
            full_proto = os.sep.join(
                ('azure_functions_worker', 'protos',
                 'azure_functions_worker', 'protos', proto)
            )
            full_protos.append(full_proto)

        os.makedirs(built_protos_dir)
        subprocess.run([
            sys.executable, '-m', 'grpc_tools.protoc',
            '-I', os.sep.join(('azure_functions_worker', 'protos')),
            '--python_out', str(built_protos_dir),
            '--grpc_python_out', str(built_protos_dir),
            *full_protos
        ], check=True, stdout=sys.stdout, stderr=sys.stderr,
            cwd=staging_root_dir)

        compiled = glob.glob(str(built_proto_files_dir / '*.py'))

        if not compiled:
            print('grpc_tools.protoc produced no Python files',
                  file=sys.stderr)
            sys.exit(1)

        for f in compiled:
            shutil.copy(f, proto_root_dir)


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
                print(
                    f"could not download Azure Functions Web Host binaries "
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
                print(r'{}', file=f)

        with open(self.extensions_dir / 'NuGet.config', 'w') as f:
            print(NUGET_CONFIG, file=f)

        env = os.environ.copy()
        env['TERM'] = 'xterm'  # ncurses 6.1 workaround

        for ext in AZURE_EXTENSIONS:
            subprocess.run([
                'func', 'extensions', 'install', '--package', ext['id'],
                '--version', ext['version']],
                check=True, cwd=str(self.extensions_dir),
                stdout=sys.stdout, stderr=sys.stderr, env=env)

    def run(self):
        self._install_webhost()
        self._install_extensions()


setup(
    name='azure-functions-worker',
    version='1.0.0b11',
    description='Python Language Worker for Azure Functions Host',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: Web Environment',
        'Development Status :: 4 - Beta',
    ],
    license='MIT',
    packages=['azure_functions_worker',
              'azure_functions_worker.protos',
              'azure_functions_worker.bindings'],
    setup_requires=[
        'grpcio~=1.20.1',
        'grpcio-tools~=1.20.1',
    ],
    install_requires=[
        'grpcio~=1.20.1',
        'grpcio-tools~=1.20.1',
    ],
    extras_require={
        'dev': [
            'azure-functions==1.0.0b5',
            'flake8~=3.5.0',
            'mypy',
            'pytest',
            'requests==2.*',
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
