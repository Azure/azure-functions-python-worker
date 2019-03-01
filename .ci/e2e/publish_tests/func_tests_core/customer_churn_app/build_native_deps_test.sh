#!/usr/bin/env bash

source "$(dirname "${BASH_SOURCE[0]}")/../helpers/helper.sh"
ensure_usage "$@"

mkdir -p "$1"
cd "$1"
git clone https://github.com/asavaritayal/customer-churn-prediction
cd customer-churn-prediction
FUNCTIONS_PYTHON_DOCKER_IMAGE=$4 "$3" azure functionapp publish "$2" --build-native-deps

if [[ $? -eq 0 ]]
then
    sleep 5s
    # https://stackoverflow.com/questions/2220301/how-to-evaluate-http-response-codes-from-bash-shell-script
    STATUS_CODE=$(curl --write-out %{http_code} --silent --output /dev/null https://$2.azurewebsites.net/api/predict)
    verify_status_code $1.result
else
    echo -e "${RED}Publishing failed (1/2)${RESET}"
    # Sometimes due to flakiness with the docker daemon or an azure resource may cause it to fail-
    # So, we retry, but just once
    echo "Retrying once....."
    FUNCTIONS_PYTHON_DOCKER_IMAGE=$4 "$3" azure functionapp publish "$2" --build-native-deps
    if [[ $? -eq 0 ]]
    then
        sleep 5s
        STATUS_CODE=$(curl --write-out %{http_code} --silent --output /dev/null https://$2.azurewebsites.net/api/predict)
        verify_status_code $1.result
    else
        echo -e "${RED}Publishing failed (2/2)${RESET}"
        echo -e "${RED}FAILED${RESET}" > $1.result
    fi
fi

cd ../..
rm -rf "$1"