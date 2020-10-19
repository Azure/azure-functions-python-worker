#!/bin/bash

HOST=$1
PORT=$2
PERF_TESTS_LINK=$3
TEST_TO_RUN=$4
PROTOCOL=http

runk6tests () {
  PROTOCOL=$PROTOCOL HOSTNAME=$1 PORT=$2 ./k6 run --summary-export=test-summary.json -q $PERF_TESTS_LINK/$TEST_TO_RUN.js
}

printresults () {
  cat test-summary.json
}

runk6tests "$HOST" "$PORT"
#printresults
