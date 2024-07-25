#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

python -m pip install .
python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

cd tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup build-protos --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"