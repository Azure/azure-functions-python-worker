import distutils.cmd
import os
import subprocess
import sys

from setuptools import setup


class GenGrpcCommand(distutils.cmd.Command):
    description = 'Generate GRPC Python bindings.'
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        cwd = os.getcwd()

        subprocess.run([
            'python', '-m', 'grpc_tools.protoc',
            '-I', os.sep.join(('azure', 'worker', 'protos')),
            '--python_out', cwd,
            '--grpc_python_out', cwd,
            os.sep.join(('azure', 'worker', 'protos',
                         'azure', 'worker', 'protos',
                         'FunctionRpc.proto')),
        ], check=True, stdout=sys.stdout, stderr=sys.stderr)


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
    packages=['azure', 'azure.worker', 'azure.functions'],
    provides=['azure'],
    include_package_data=True,
    cmdclass={
        'gen_grpc': GenGrpcCommand
    },
    test_suite='azure.worker.tests'
)
