import os
import sys

from pathlib import Path

# User packages
PKGS_PATH = "site/wwwroot/.python_packages"
VENV_PKGS_PATH = "site/wwwroot/worker_venv"

PKGS_36 = "lib/python3.6/site-packages"
PKGS = "lib/site-packages"

# Azure environment variables
AZURE_WEBSITE_INSTANCE_ID = "WEBSITE_INSTANCE_ID"
AZURE_CONTAINER_NAME = "CONTAINER_NAME"
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"


def is_azure_environment():
    """Check if the function app is running on the cloud"""
    return (AZURE_CONTAINER_NAME in os.environ
            or AZURE_WEBSITE_INSTANCE_ID in os.environ)


def add_script_root_to_sys_path():
    """Append function project root to module finding sys.path"""
    functions_script_root = os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT)
    if functions_script_root is not None:
        sys.path.append(functions_script_root)


def determine_user_pkg_paths():
    """This finds the user packages when function apps are running on the cloud

    For Python 3.6 app, the third-party packages can live in any of the paths:
        /home/site/wwwroot/.python_packages/lib/site-packages
        /home/site/wwwroot/.python_packages/lib/python3.6/site-packages
        /home/site/wwwroot/worker_venv/lib/python3.6/site-packages

    For Python 3.7, we only accept:
        /home/site/wwwroot/.python_packages/lib/site-packages
    """
    minor_version = sys.version_info[1]

    home = Path.home()
    pkgs_path = os.path.join(home, PKGS_PATH)
    venv_pkgs_path = os.path.join(home, VENV_PKGS_PATH)

    user_pkg_paths = []
    if minor_version == 6:
        user_pkg_paths.append(os.path.join(venv_pkgs_path, PKGS_36))
        user_pkg_paths.append(os.path.join(pkgs_path, PKGS_36))
        user_pkg_paths.append(os.path.join(pkgs_path, PKGS))
    elif minor_version == 7:
        user_pkg_paths.append(os.path.join(pkgs_path, PKGS))
    else:
        raise RuntimeError(f'Unsupported Python version: 3.{minor_version}')

    return user_pkg_paths


if __name__ == '__main__':
    # worker.py lives in the same directory as azure_functions_worker
    func_worker_dir = str(Path(__file__).absolute().parent)
    env = os.environ

    if is_azure_environment():
        user_pkg_paths = determine_user_pkg_paths()

        joined_pkg_paths = os.pathsep.join(user_pkg_paths)

        # On cloud, we prioritize third-party user packages
        # over worker packages in PYTHONPATH
        env['PYTHONPATH'] = f'{joined_pkg_paths}:{func_worker_dir}'
        os.execve(sys.executable,
                  [sys.executable, '-m', 'azure_functions_worker']
                  + sys.argv[1:],
                  env)
    else:
        # On local development, we prioritize worker packages over
        # third-party user packages (in .venv)
        sys.path.insert(1, func_worker_dir)
        add_script_root_to_sys_path()
        from azure_functions_worker import main

        main.main()
