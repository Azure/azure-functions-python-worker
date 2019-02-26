#!/usr/bin/env bash

# Get the configuration variables
source "$(dirname "${BASH_SOURCE[0]}")/../helpers/get_config_variables.sh"

FUNCTION_APP="$(cat "${GLOBAL_CONFIG}" | jq -r '.publish_function_app.prod_func_dev_docker.customer_churn.build_native_deps')"

"$(dirname "${BASH_SOURCE[0]}")/../../func_tests_core/customer_churn_app/build_native_deps_test.sh" ${WORKING_DIR}/pfddcbnd ${FUNCTION_APP} func ${DEV_DOCKER_IMAGE}