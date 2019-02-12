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
FUNCTIONS_PYTHON_DOCKER_IMAGE=$4 "$3" azure functionapp publish "$2"

if [[ $? -eq 0 ]]
then
    # https://stackoverflow.com/questions/2220301/how-to-evaluate-http-response-codes-from-bash-shell-script
    STATUS_CODE=$(curl --write-out %{http_code} --silent --output /dev/null https://$2.azurewebsites.net/api/httptriggerTest?name=test)
    verify_status_code $1.result
else
    echo "Publishing failed"
    echo -e "${RED}FAILED${RESET}" > $1.result
fi

deactivate
cd ..
rm -rf "$1"