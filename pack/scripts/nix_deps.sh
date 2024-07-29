#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

python -m pip install .
python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"
cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"