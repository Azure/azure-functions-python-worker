#!/bin/bash

set -e -x
pytest  --instafail --cov=./azure_functions_worker --cov-report xml --cov-branch tests/unittests