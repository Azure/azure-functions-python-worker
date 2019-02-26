#!/usr/bin/env bash

# Get the configuration variables
source "$(dirname "${BASH_SOURCE[0]}")/../helpers/get_config_variables.sh"

FUNCTION_APP="$(cat "${GLOBAL_CONFIG}" | jq -r '.publish_function_app.prod_func_dev_docker.new_function.packapp')"

"$(dirname "${BASH_SOURCE[0]}")/../../func_tests_core/new_functionapp/packapp_test.sh" ${WORKING_DIR}/pfddnpa ${FUNCTION_APP} func ${DEV_DOCKER_IMAGE}
