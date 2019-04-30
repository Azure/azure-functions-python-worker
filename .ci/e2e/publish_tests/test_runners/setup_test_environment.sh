#!/usr/bin/env bash

set -e
# Get the configuration variables
source "$(dirname "${BASH_SOURCE[0]}")/helpers/get_config_variables.sh"

# Login to the Service Principal Azure Account
az login --service-principal -u ${SP_USER_NAME} -p ${SP_PASSWORD} --tenant ${SP_TENANT} --output none

# Update the ACR Docker Image with the dev branch of Docker image and python worker
chmod a+x $(dirname "${BASH_SOURCE[0]}")/../dev_docker_setup/setup.sh
$(dirname "${BASH_SOURCE[0]}")/../dev_docker_setup/setup.sh ${ACR_NAME} ${DEV_IMAGE_NAME} ${DOCKER_WORKING_DIR}

# Setup the dev func executables
chmod a+x $(dirname "${BASH_SOURCE[0]}")/../dev_func_setup/setup.sh
$(dirname "${BASH_SOURCE[0]}")/../dev_func_setup/setup.sh ${FUNC_DEV_DIR} ${FUNC_DEV_URL}