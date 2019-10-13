import os
import sys
import platform
import subprocess
from pathlib import Path

# User packages
PKGS_PATH = "site/wwwroot/.python_packages"
VENV_PKGS_PATH = "site/wwwroot/worker_venv"

PKGS_36 = "lib/python3.6/site-packages"
PKGS = "lib/site-packages"

# Azure environment variables
AZURE_WEBSITE_INSTANCE_ID = "WEBSITE_INSTANCE_ID"
AZURE_CONTAINER_NAME = "CONTAINER_NAME"


def is_azure_environment():
    return (AZURE_CONTAINER_NAME in os.environ or
            AZURE_WEBSITE_INSTANCE_ID in os.environ)


def determine_user_pkg_paths():
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
    user_pkg_paths = []
    if is_azure_environment():
        user_pkg_paths = determine_user_pkg_paths()

    env = os.environ
    # worker.py lives in the same directory as azure_functions_worker
    func_worker_dir = str(Path(__file__).absolute().parent)

    if platform.system() == 'Windows':
        joined_pkg_paths = ";".join(user_pkg_paths)
        env['PYTHONPATH'] = f'{joined_pkg_paths};{func_worker_dir}'
        # execve doesn't work in Windows: https://bugs.python.org/issue19124
        subprocess.run([sys.executable,
                       '-m', 'azure_functions_worker'] + sys.argv[1:],
                       env=env)
    else:
        joined_pkg_paths = ":".join(user_pkg_paths)
        env['PYTHONPATH'] = f'{joined_pkg_paths}:{func_worker_dir}'
        os.execve(sys.executable,
                  [sys.executable, '-m', 'azure_functions_worker']
                  + sys.argv[1:],
                  env)
