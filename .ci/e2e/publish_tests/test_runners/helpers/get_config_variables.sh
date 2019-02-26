#!/usr/bin/env bash

# Get the configuration file
GLOBAL_CONFIG="$(dirname "${BASH_SOURCE[0]}")/../../publish_config.json"
if [[ -n "$1" ]]
then
    echo "Using the provided global config"
    GLOBAL_CONFIG=$1
fi

# Docker Dev Variables
DOCKER_CONFIG="$(cat "${GLOBAL_CONFIG}" | jq '.docker_setup')"
ACR_NAME="$(echo "${DOCKER_CONFIG}" | jq -r '.acr_name')"
DEV_IMAGE_NAME="$(echo "${DOCKER_CONFIG}" | jq -r '.dev_image_name')"
DEV_DOCKER_IMAGE=${ACR_NAME}.azurecr.io/${DEV_IMAGE_NAME}
DOCKER_WORKING_DIR="$(echo "${DOCKER_CONFIG}" | jq -r '.working_dir')"

# Docker Prod Variables
PROD_DOCKER_IMAGE="$(echo "${DOCKER_CONFIG}" | jq -r '.prod_image')"

# Func Dev Variables
FUNC_CONFIG="$(cat "${GLOBAL_CONFIG}" | jq '.func_setup')"
FUNC_DEV_DIR="$(echo "${FUNC_CONFIG}" | jq -r '.func_dev_dir')"
FUNC_DEV_URL="$(echo "${FUNC_CONFIG}" | jq -r '.func_dev_url')"

# Working dir variables
TESTS_CONFIG="$(cat "${GLOBAL_CONFIG}" | jq '.tests')"
WORKING_DIR="$(echo "${TESTS_CONFIG}" | jq -r '.working_dir')"
TESTS_LOGS="$(echo "${TESTS_CONFIG}" | jq -r '.logs')"
TESTS_TIMEOUT="$(echo "${TESTS_CONFIG}" | jq -r '.timeout')"

# Service Principal variables
SP_CONFIG="$(cat "${GLOBAL_CONFIG}" | jq '.azure_service_principal')"
SP_USER_NAME="$(echo "${SP_CONFIG}" | jq -r '.user_id')"
SP_PASSWORD="$(echo "${SP_CONFIG}" | jq -r '.password')"
SP_TENANT="$(echo "${SP_CONFIG}" | jq -r '.tenant')"
