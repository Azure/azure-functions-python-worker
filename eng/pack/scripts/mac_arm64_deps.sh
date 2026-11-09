#!/bin/bash

set -euo pipefail

# macOS-latest supplies x64 build tools, even for an ARM64 artifact. Keep
# proto generation on the host, but resolve staged wheels for the target.
architecture=${2:-x64}
target_args=(--no-compile)
case "$architecture" in
    x64) native_arch=x86_64 ;;
    arm64)
        native_arch=arm64
        target_args+=(--platform macosx_11_0_arm64 --only-binary=:all:)
        ;;
    *) echo "Unsupported macOS architecture: $architecture" >&2; exit 1 ;;
esac

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip
python -m pip install "setuptools>=62,<82.0"

cd workers
python -m pip install .
python -m pip install . "${target_args[@]}" --target "$BUILD_SOURCESDIRECTORY/deps"

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

# A darwin.so filename does not identify its CPU architecture. Check every
# staged extension/library, including universal2 binaries, without loading it.
while IFS= read -r -d '' binary; do
    lipo -verify_arch "$native_arch" "$binary"
done < <(find "$BUILD_SOURCESDIRECTORY/deps" -type f \( -name '*.so' -o -name '*.dylib' \) -print0)