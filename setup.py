import os
import subprocess
import sys
from distutils.command import build

from setuptools import setup
from setuptools.command import develop


class BuildGRPC:
    """Generate gRPC bindings."""
    def _gen_grpc(self):
        cwd = os.getcwd()

        subprocess.run([
            sys.executable, '-m', 'grpc_tools.protoc',
            '-I', os.sep.join(('azure', 'worker', 'protos')),
            '--python_out', cwd,
            '--grpc_python_out', cwd,
            os.sep.join(('azure', 'worker', 'protos',
                         'azure', 'worker', 'protos',
                         'FunctionRpc.proto')),
        ], check=True, stdout=sys.stdout, stderr=sys.stderr)


class build(build.build, BuildGRPC):
    def run(self, *args, **kwargs):
        self._gen_grpc()
        super().run(*args, **kwargs)


class develop(develop.develop, BuildGRPC):
    def run(self, *args, **kwargs):
        self._gen_grpc()
        super().run(*args, **kwargs)


setup(
    name='azure',
    version='0.0.1',
    description='Azure Python Functions',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: Microsoft :: Windows',
        'Operating System :: POSIX',
        'Operating System :: MacOS :: MacOS X',
        'Environment :: Web Environment',
        'Development Status :: 3 - Alpha',
    ],
    license='MIT',
    packages=['azure', 'azure.functions',
              'azure.worker', 'azure.worker.protos'],
    provides=['azure'],
    install_requires=[
        'grpcio',
        'grpcio-tools',
    ],
    extras_require={
        'dev': [
            'pytest',
            'requests',
            'mypy',
            'flake8',
        ]
    },
    include_package_data=True,
    cmdclass={
        'build': build,
        'develop': develop
    },
    test_suite='tests'
)
