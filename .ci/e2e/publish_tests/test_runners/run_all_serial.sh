#!/bin/bash

# Get the config file
source "$(dirname "${BASH_SOURCE[0]}")/helpers/get_config_variables.sh"
source "$(dirname "${BASH_SOURCE[0]}")/helpers/helper.sh"

mkdir -p ${WORKING_DIR}
mkdir -p ${TESTS_LOGS}

BASE_DIR="$(dirname "${BASH_SOURCE[0]}")"
RESET='\033[0m' # No Color
BLUE='\033[1;34m'
YELLOW='\033[1;33m'

# This may be needed if docker image is restarted
# Better to simply login again at every invoke
echo "Ensuring login to Azure ACR"
az acr login --name ${ACR_NAME} --output none

echo -e "Starting Serial Execution..."
echo "This will take a while"


run_test ${BASE_DIR}/dev_func_dev_docker/customer_build_native_deps.sh ${TESTS_LOGS}/dfddcbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfddcbnd.result
run_test ${BASE_DIR}/dev_func_dev_docker/customer_no_bundler.sh ${TESTS_LOGS}/dfddcnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfddcnb.result
run_test ${BASE_DIR}/dev_func_dev_docker/new_build_native_deps.sh ${TESTS_LOGS}/dfddnbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfddnbnd.result
run_test ${BASE_DIR}/dev_func_dev_docker/new_no_bundler.sh ${TESTS_LOGS}/dfddnnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfddnnb.result
run_test ${BASE_DIR}/dev_func_dev_docker/new_packapp.sh ${TESTS_LOGS}/dfddnpa.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfddnpa.result

run_test ${BASE_DIR}/dev_func_prod_docker/customer_build_native_deps.sh ${TESTS_LOGS}/dfpdcbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfpdcbnd.result
run_test ${BASE_DIR}/dev_func_prod_docker/customer_no_bundler.sh ${TESTS_LOGS}/dfpdcnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfpdcnb.result
run_test ${BASE_DIR}/dev_func_prod_docker/new_build_native_deps.sh ${TESTS_LOGS}/dfpdnbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfpdnbnd.result
run_test ${BASE_DIR}/dev_func_prod_docker/new_no_bundler.sh ${TESTS_LOGS}/dfpdnnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfpdnnb.result
run_test ${BASE_DIR}/dev_func_prod_docker/new_packapp.sh ${TESTS_LOGS}/dfpdnpa.log ${TESTS_TIMEOUT} ${WORKING_DIR}/dfpdnpa.result

run_test ${BASE_DIR}/prod_func_prod_docker/customer_build_native_deps.sh ${TESTS_LOGS}/pfpdcbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfpdcbnd.result
run_test ${BASE_DIR}/prod_func_prod_docker/customer_no_bundler.sh ${TESTS_LOGS}/pfpdcnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfpdcnb.result
run_test ${BASE_DIR}/prod_func_prod_docker/new_build_native_deps.sh ${TESTS_LOGS}/pfpdnbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfpdnbnd.result
run_test ${BASE_DIR}/prod_func_prod_docker/new_no_bundler.sh ${TESTS_LOGS}/pfpdnnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfpdnnb.result
run_test ${BASE_DIR}/prod_func_prod_docker/new_packapp.sh ${TESTS_LOGS}/pfpdnpa.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfpdnpa.result

echo "Ensuring login to Azure ACR (again because login has been flaky)"
az acr login --name ${ACR_NAME} --output none
run_test ${BASE_DIR}/prod_func_dev_docker/customer_build_native_deps.sh ${TESTS_LOGS}/pfddcbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfddcbnd.result
run_test ${BASE_DIR}/prod_func_dev_docker/customer_no_bundler.sh ${TESTS_LOGS}/pfddcnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfddcnb.result
run_test ${BASE_DIR}/prod_func_dev_docker/new_build_native_deps.sh ${TESTS_LOGS}/pfddnbnd.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfddnbnd.result
run_test ${BASE_DIR}/prod_func_dev_docker/new_no_bundler.sh ${TESTS_LOGS}/pfddnnb.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfddnnb.result
run_test ${BASE_DIR}/prod_func_dev_docker/new_packapp.sh ${TESTS_LOGS}/pfddnpa.log ${TESTS_TIMEOUT} ${WORKING_DIR}/pfddnpa.result

echo "Test Completed!"
yellow "Results-"
printf "\n"

print_row $(yellow "Version") $(yellow "Exist-Build-Native") \
$(yellow "Exist-No-Bundler") $(yellow "New-Build-Native") $(yellow "New-No-Bundler") $(yellow "New-Packapp")

print_row_line

print_row $(yellow "dev-func-dev-docker") $(get_result_of ${WORKING_DIR}/dfddcbnd.result) \
$(get_result_of ${WORKING_DIR}/dfddcnb.result) $(get_result_of ${WORKING_DIR}/dfddnbnd.result) \
$(get_result_of ${WORKING_DIR}/dfddnnb.result) $(get_result_of ${WORKING_DIR}/dfddnpa.result)

print_row $(yellow "dev-func-prod-docker") $(get_result_of ${WORKING_DIR}/dfpdcbnd.result) \
$(get_result_of ${WORKING_DIR}/dfpdcnb.result) $(get_result_of ${WORKING_DIR}/dfpdnbnd.result) \
$(get_result_of ${WORKING_DIR}/dfpdnnb.result) $(get_result_of ${WORKING_DIR}/dfpdnpa.result)

print_row $(yellow "prod-func-dev-docker") $(get_result_of ${WORKING_DIR}/pfddcbnd.result) \
$(get_result_of ${WORKING_DIR}/pfddcnb.result) $(get_result_of ${WORKING_DIR}/pfddnbnd.result) \
$(get_result_of ${WORKING_DIR}/pfddnnb.result) $(get_result_of ${WORKING_DIR}/pfddnpa.result)

print_row $(yellow "prod-func-prod-docker") $(get_result_of ${WORKING_DIR}/pfpdcbnd.result) \
$(get_result_of ${WORKING_DIR}/pfpdcnb.result) $(get_result_of ${WORKING_DIR}/pfpdnbnd.result) \
$(get_result_of ${WORKING_DIR}/pfpdnnb.result) $(get_result_of ${WORKING_DIR}/pfpdnpa.result)

printf "\n"
echo "All logs are available at ${TESTS_LOGS}"

if [[ ${ENVIRONMENT} = "DOCKER" ]]
then
    # This is useful when running in a container environment
    echo "Sleeping for infinity, in case you need to open bash in the container"
    sleep infinity
fi

if [[ -z ${EXIT_ON_FAIL} ]] || [[ ${EXIT_ON_FAIL} -ne "FALSE" ]]
then
    NUMBER_PASSED=$(grep -l "PASSED" ${WORKING_DIR}/*.result | wc -l)
    if [[ ${NUMBER_PASSED} -ne 20 ]]
    then
        echo "Not all (20) tests passed! Dieing.."
        exit 1
    else
        echo "All tests passed (20/20)!"
    fi
fi