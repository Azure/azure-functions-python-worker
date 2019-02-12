#!/usr/bin/env bash

USAGE="usage ./script <directory_name> <appname> <func_location> <docker_image>"
# https://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux
RED='\033[0;31m'
GREEN='\033[0;32m'
RESET='\033[0m' # No Color

ensure_usage() {

    if [[ -z "$1" ]]
    then
        echo "Missing name of the directory"
        echo ${USAGE}
        exit 1
    fi

    if [[ -z "$2" ]]
    then
        echo "Missing name of the functions app to publish"
        echo ${USAGE}
        exit 1
    fi

    if [[ -z "$3" ]]
    then
        echo "Missing name of the func executable"
        echo ${USAGE}
        exit 1
    fi

    if [[ -z "$4" ]]
    then
        echo "Missing name of the docker image to use"
        echo ${USAGE}
        exit 1
    fi

}

# Assuming Status_code is set
verify_status_code() {
    if [[ -z "$1" ]]
    then
        echo "Missing name of the log file"
        exit 1
    fi
    if [[ "${STATUS_CODE}" -ne 200 ]]
    then
        MESSAGE="${RED}TEST FAILED: Expected Status Code 200. Found Status Code ${STATUS_CODE}${RESET}"
        (>&2 echo -e ${MESSAGE})
        echo -e "${RED}FAILED${RESET}" > $1
    else
        MESSAGE="${GREEN}TEST PASSED: Status Code 200.${RESET}"
        echo -e ${MESSAGE}
        echo -e "${GREEN}PASSED${RESET}" > $1
    fi
}

fail_after_timeout() {
    timeout $1 ${@:2}
}