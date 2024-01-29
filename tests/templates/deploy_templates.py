import os
import re
import subprocess

subscription_id = "0b894477-1614-4c8d-8a9b-a697a24596b8"
resource_group = "AzureFunctionsPythonWorkerCILinuxDevOps"


def deploy_bicep_files():
    """
    Deploy selected Bicep files compatible with the specified Python version to the given Azure resource group,
    with user-provided parameters for each template.

    :param resource_group: The Azure resource group to deploy to.
    :param python_version: The Python version to filter Bicep files.
    """
    # Get the current working directory
    directory = os.getcwd()

    python_version = input("Enter the Python version (e.g., 3.8): ")

    # Regex pattern to match files compatible with the specified Python version
    pattern = ".*\\.bicep$"

    # List all Bicep files in the directory compatible with the specified Python version
    all_bicep_files = [f for f in os.listdir(directory) if re.search(pattern, f)]

    if not all_bicep_files:
        print(f"No Bicep files found")
        return

    # Display the list of files to the user
    print("Available Bicep Templates:")
    for idx, file in enumerate(all_bicep_files, 1):
        print(f"{idx}. {file}")

    # Ask user to select files to deploy
    selected = input("Enter the numbers of the templates to deploy (comma separated), or type 'all' to deploy all: ")
    if selected.lower() == 'all':
        bicep_files_to_deploy = all_bicep_files
    else:
        selected_indices = [int(i) - 1 for i in selected.split(',') if i.isdigit()]
        bicep_files_to_deploy = [all_bicep_files[i] for i in selected_indices if 0 <= i < len(all_bicep_files)]

    # Deploy the selected Bicep files
    for bicep_file in bicep_files_to_deploy:
        file_path = os.path.join(directory, bicep_file)

        params_string = f"--parameters python_version={python_version.replace('.', '')}"

        # Deploy the Bicep file
        print(f"Deploying {bicep_file}...")
        deploy_command = (f"az deployment group create --subscription {subscription_id} "
                          f"--resource-group {resource_group}  --template-file {file_path} {params_string}")
        subprocess.run(deploy_command, shell=True)


deploy_bicep_files()
