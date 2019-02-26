#!/usr/bin/env bash

# Get the configuration variables
source "$(dirname "${BASH_SOURCE[0]}")/../helpers/get_config_variables.sh"

FUNCTION_APP="$(cat "${GLOBAL_CONFIG}" | jq -r '.publish_function_app.prod_func_prod_docker.customer_churn.no_bundler')"

"$(dirname "${BASH_SOURCE[0]}")/../../func_tests_core/customer_churn_app/no_bundler_test.sh" ${WORKING_DIR}/pfpdcnb ${FUNCTION_APP} func ${PROD_DOCKER_IMAGE}