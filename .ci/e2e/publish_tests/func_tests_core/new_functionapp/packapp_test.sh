#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/../helpers/helper.sh"
ensure_usage "$@"

# Setup a new func app from prod func
mkdir -p "$1"
cd "$1"
python -m venv env_new_build_native
source env_new_build_native/bin/activate
"$3" init . --worker-runtime python
"$3" new --template httptrigger --name httptriggerTest

# Change auth level to anonymous
jq '.bindings[].authLevel="anonymous"' httptriggerTest/function.json  > httptriggerTest/replaced.json
mv httptriggerTest/replaced.json httptriggerTest/function.json

# Publish and verify
FUNCTIONS_PYTHON_DOCKER_IMAGE=$4 "$3" azure functionapp publish "$2"

if [[ $? -eq 0 ]]
then
    # https://stackoverflow.com/questions/2220301/how-to-evaluate-http-response-codes-from-bash-shell-script
    STATUS_CODE=$(curl --write-out %{http_code} --silent --output /dev/null https://$2.azurewebsites.net/api/httptriggerTest?name=test)
    verify_status_code $1.result
else
    echo -e "${RED}Publishing failed (1/2)${RESET}"
    # Sometimes due to flakiness with the docker daemon or an azure resource may cause it to fail-
    # So, we retry, but just once
    echo "Retrying once....."
    FUNCTIONS_PYTHON_DOCKER_IMAGE=$4 "$3" azure functionapp publish "$2"
    if [[ $? -eq 0 ]]
    then
        STATUS_CODE=$(curl --write-out %{http_code} --silent --output /dev/null https://$2.azurewebsites.net/api/httptriggerTest?name=test)
        verify_status_code $1.result
    else
        echo -e "${RED}Publishing failed (2/2)${RESET}"
        echo -e "${RED}FAILED${RESET}" > $1.result
    fi
fi

deactivate
cd ..
rm -rf "$1"