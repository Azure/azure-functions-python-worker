#!/bin/bash

echo "=== Upgrading pip and installing build dependencies ==="
python -m pip install --upgrade pip setuptools wheel cython

echo "=== Cloning gRPC repo ==="
rm -rf grpc
git clone --recursive https://github.com/grpc/grpc

echo "=== Building grpcio wheel from source ==="
cd grpc
git submodule update --init --recursive
export GRPC_PYTHON_BUILD_WITH_CYTHON=1

# Build the wheel into dist/
python -m pip wheel . -w dist

# Log contents of dist
echo "=== Checking dist directory ==="
if [ -d dist ]; then
    ls -lh dist
else
    echo "dist/ directory not found!"
fi

# Log and install grpcio
GRPC_WHEEL=$(ls dist/grpcio-*.whl | head -n 1)
echo "Built grpcio wheel: $(basename "$GRPC_WHEEL")"
echo "=== Install grpcio wheel $(basename "$GRPC_WHEEL") into root ==="
python -m pip install "$GRPC_WHEEL"

cd ..

# Change back to project root
cd workers

echo "=== Install other deps into root ==="
python -m pip install .
python -m pip install grpcio-tools==1.70.0

echo "=== Installing grpcio into deps/ ==="
python -m pip install "$GRPC_WHEEL" --target "$BUILD_SOURCESDIRECTORY/deps"

echo "=== Installing other deps into deps/ ==="
python -m pip install --upgrade pip setuptools wheel cython --target "$BUILD_SOURCESDIRECTORY/deps"
python -m pip install . azure-functions --no-compile --target "$BUILD_SOURCESDIRECTORY/deps" --find-links ../grpc/dist
python -m pip install grpcio-tools==1.70.0 --no-compile --target "$BUILD_SOURCESDIRECTORY/deps" --find-links ../grpc/dist

echo "=== Install invoke and build protos ==="
python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

echo "=== Copying .artifactignore ==="
cd ..
cp .artifactignore "$BUILD_SOURCESDIRECTORY/deps"

echo "=== Copying protos ==="
version_minor=$(echo $1 | cut -d '.' -f 2)
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$BUILD_SOURCESDIRECTORY/deps/azure_functions_worker"
else
    cp -r proxy_worker/protos "$BUILD_SOURCESDIRECTORY/deps/proxy_worker"
fi