# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import pathlib
import sys

PKGS_PATH = "/home/site/wwwroot/.python_packages"
PKGS = "lib/site-packages"

# Azure environment variables
AZURE_WEBSITE_INSTANCE_ID = "WEBSITE_INSTANCE_ID"
AZURE_CONTAINER_NAME = "CONTAINER_NAME"
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"


def is_azure_environment():
    """Check if the function app is running on the cloud"""
    return (AZURE_CONTAINER_NAME in os.environ
            or AZURE_WEBSITE_INSTANCE_ID in os.environ)


def validate_python_version():
    minor_version = sys.version_info[1]
    if not (13 <= minor_version < 15):
        raise RuntimeError(f'Unsupported Python version: 3.{minor_version}')


def determine_user_pkg_paths():
    """This finds the user packages when function apps are running on the cloud
        User packages are defined in:
            /home/site/wwwroot/.python_packages/lib/site-packages
    """
    usr_packages_path = [os.path.join(PKGS_PATH, PKGS)]
    return usr_packages_path


def add_script_root_to_sys_path():
    """Append function project root to module finding sys.path"""
    functions_script_root = os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT)
    if functions_script_root is not None:
        sys.path.append(functions_script_root)


if __name__ == '__main__':
    validate_python_version()
    func_worker_dir = str(pathlib.Path(__file__).absolute().parent)
    env = os.environ

    # Setting up python path for all environments to prioritize
    # third-party user packages over worker packages in PYTHONPATH
    user_pkg_paths = determine_user_pkg_paths()
    joined_pkg_paths = os.pathsep.join(user_pkg_paths)
    env['PYTHONPATH'] = f'{joined_pkg_paths}:{func_worker_dir}'

    project_root = os.path.abspath(os.path.dirname(__file__))
    if project_root not in sys.path:
        sys.path.append(project_root)

    if is_azure_environment():
        os.execve(sys.executable,
                  [sys.executable, '-m', 'proxy_worker']
                  + sys.argv[1:],
                  env)
    else:
        add_script_root_to_sys_path()
        from proxy_worker import start_worker
        start_worker.start()
