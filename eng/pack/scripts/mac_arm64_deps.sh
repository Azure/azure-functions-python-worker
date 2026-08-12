#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip
python -m pip install "setuptools>=62,<82.0"

cd workers
python -m pip install .
python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"

version_minor=$(echo $1 | cut -d '.' -f 2)
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"
    # Vendored google.protobuf is built into the source tree by vendor_deps
    # (invoked from build-protos). Merge it into deps/ so CopyFiles@2 picks it up.
    mkdir -p "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker/_vendored"
    cp -r azure_functions_worker/_vendored/. "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker/_vendored/"
else
    cp -r proxy_worker/protos "$BUILD_SOURCESDIRECTORY/deps/proxy_worker"
fi