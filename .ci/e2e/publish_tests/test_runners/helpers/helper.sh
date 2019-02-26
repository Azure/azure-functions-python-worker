#!/usr/bin/env bash

RESET='\033[0m' # No Color
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
RED='\033[0;31m'


yellow() {
    echo -e "${YELLOW}$1${RESET}"
}
get_result_of() {
    if [[ -z "$1" ]]
    then
        echo -e "${RED}FAILED${RESET}"
    elif [[ ! -f "$1" ]]
    then
        echo -e "${ORANGE}SKIPPED${RESET}"
    else
        cat "$1"
    fi
}

print_row_line() {
    # (32 (-10 for colors) + 4) * 6 args + 1 for beauty
    row=$(printf "%157s" "-")
    echo "${row// /-}"
}

print_row() {
    printf "%-4s" "|"
    for arg in "$@"
    do
        printf "%-32s %-4s" ${arg} "|"
    done
    printf "\n"
}

# Expects a test_script, test_log, timeout, test_result
run_test() {
    exit_code=0
    set -o pipefail
    chmod a+x $1
    if [[ ${TESTS_VERBOSE} = "SILENT" ]]
    then
        timeout $3 $1 > $2
        exit_code=$?
    else
        timeout $3 $1 2>&1 | tee $2
        exit_code=$?
    fi
    # This means we had a timeout
    if [[ ${exit_code} = 124 ]]
    then
        echo "Test Timed Out!"
        echo -e "${ORANGE}TIMEOUT${RESET}" > $4
    fi
}

