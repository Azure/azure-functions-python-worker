#!/usr/bin/env bash

# Get the configuration variables
source "$(dirname "${BASH_SOURCE[0]}")/../helpers/get_config_variables.sh"

FUNCTION_APP="$(cat "${GLOBAL_CONFIG}" | jq -r '.publish_function_app.prod_func_prod_docker.new_function.build_native_deps')"

"$(dirname "${BASH_SOURCE[0]}")/../../func_tests_core/new_functionapp/build_native_deps_test.sh" ${WORKING_DIR}/pfpdnbnd ${FUNCTION_APP} func ${PROD_DOCKER_IMAGE}