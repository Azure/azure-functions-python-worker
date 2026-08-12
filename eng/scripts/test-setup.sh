#!/bin/bash
set -e

cd workers/tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup webhost --branch-name=dev
python -m invoke -c test_setup extensions