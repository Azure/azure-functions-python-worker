import sys
import os
from azure_functions_worker import main


# Azure environment variables
AZURE_WEBJOBS_SCRIPT_ROOT = "AzureWebJobsScriptRoot"


def add_script_root_to_sys_path():
    '''Append function project root to module finding sys.path'''
    functions_script_root = os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT)
    if functions_script_root is not None:
        sys.path.append(functions_script_root)


if __name__ == '__main__':
    add_script_root_to_sys_path()
    main.main()
