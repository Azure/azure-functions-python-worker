#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

cd workers
python -m pip install .
python -m pip install grpcio~=1.70.0
python -m pip install grpcio-tools~=1.70.0

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"
python -m pip install grpcio~=1.70.0 --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"
python -m pip install grpcio-tools~=1.70.0 --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"

version_minor=$(echo $1 | cut -d '.' -f 2)
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"
else
    cp -r proxy_worker/protos "$BUILD_SOURCESDIRECTORY/deps/proxy_worker"
fi