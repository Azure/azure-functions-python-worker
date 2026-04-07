#!/bin/bash
# This script installs ARM64 Python dependencies without Docker
# Uses pip's --platform flag to download ARM64-specific wheels

set -e

PYTHON_VERSION=$1
version_minor=$(echo $PYTHON_VERSION | cut -d '.' -f 2)

echo "Building ARM64 dependencies for Python version: $PYTHON_VERSION (minor: $version_minor)"

# Create deps directory
mkdir -p $BUILD_SOURCESDIRECTORY/deps

# Setup Python environment
python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip
python -m pip install setuptools==81.0

echo "Installing build tools (which must be platform-compatible)..."
pip install grpcio-tools invoke

# Navigate to workers directory
cd workers

# Create temp directory for downloading ARM64 wheels
mkdir -p /tmp/arm64_wheels

# Download ARM64 wheels for the specific Python version
echo "Downloading ARM64 wheels for Python ${PYTHON_VERSION}..."
pip download \
    --platform manylinux_2_17_aarch64 \
    --only-binary=:all: \
    --dest /tmp/arm64_wheels \
    .

# List downloaded wheels for debugging
echo "Downloaded wheels:"
ls -la /tmp/arm64_wheels/

# Install ARM64 wheels from the downloaded files
echo "Installing ARM64 dependencies from downloaded wheels..."
# Extract wheel files manually to bypass platform compatibility checks
# Wheels are just ZIP archives, so we can extract them directly
for wheel in /tmp/arm64_wheels/*.whl; do
    echo "Extracting $wheel..."
    unzip -o -q "$wheel" -d $BUILD_SOURCESDIRECTORY/deps
done

# Remove .dist-info directories to avoid conflicts
rm -rf $BUILD_SOURCESDIRECTORY/deps/*.dist-info

# Build protos
cd tests
python -m invoke -c test_setup build-protos
cd ..

echo "Current working directory after building protos & cd-ing one level back: $(pwd)"
ls -la


# Copy .artifactignore
if [ -f .artifactignore ]; then
  cp .artifactignore $BUILD_SOURCESDIRECTORY/deps
fi

# Copy protos based on Python version
if [[ $version_minor -lt 13 ]]; then
  echo "Copying azure_functions_worker protos..."
  mkdir -p $BUILD_SOURCESDIRECTORY/deps/azure_functions_worker
  cp -r azure_functions_worker/protos $BUILD_SOURCESDIRECTORY/deps/azure_functions_worker
else
  echo "Copying proxy_worker protos..."
  mkdir -p $BUILD_SOURCESDIRECTORY/deps/proxy_worker
  cp -r proxy_worker/protos $BUILD_SOURCESDIRECTORY/deps/proxy_worker
fi

echo "ARM64 dependencies installed successfully!"
echo "Listing contents of deps directory:"
ls -la $BUILD_SOURCESDIRECTORY/deps