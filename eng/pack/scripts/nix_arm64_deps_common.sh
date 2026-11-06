#!/bin/bash
# Build on the agent architecture, then download the matching ARM64 runtimes.
set -euo pipefail

PYTHON_VERSION=${1:?A Python version is required}
repo_root=${BUILD_SOURCESDIRECTORY:?BUILD_SOURCESDIRECTORY is required}
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

cd "$repo_root"
python -m venv "$work_dir/build-env"
source "$work_dir/build-env/bin/activate"
python -m pip install --upgrade pip
python -m pip install 'setuptools>=62,<82.0' wheel

# Use the version selected by UsePythonVersion, including for RC builds.
python -c 'import re, sys; assert re.match(r"\d+\.\d+", sys.argv[1])[0] == "%d.%d" % sys.version_info[:2], "Build interpreter does not match requested Python"' "$PYTHON_VERSION"
version_minor=$(python -c 'import sys; print(sys.version_info.minor)')

cd workers
# Resolve build tools through the worker's Python-version-specific requirements,
# not an unconstrained grpcio-tools install that can emit newer gencode.
python -m pip install . invoke
python -c 'from importlib.metadata import version; print("\n".join(name + "==" + version(name) for name in ("grpcio", "grpcio-tools", "protobuf")))' > "$work_dir/proto-constraints.txt"

cd tests
python -m invoke -c test_setup build-protos
cd ..

# pip download . saves dependencies, but does NOT build/save the local project.
# Build it explicitly and make that wheel the input to dependency resolution.
python -m pip wheel --no-deps --wheel-dir "$work_dir/worker-wheel" .
python -m pip download \
    --platform manylinux_2_17_aarch64 \
    --only-binary=:all: \
    --constraint "$work_dir/proto-constraints.txt" \
    --dest "$work_dir/arm64-wheels" \
    "$work_dir/worker-wheel"/*.whl

# Start clean: stale modules or native extensions must not mask missing files.
rm -rf "$repo_root/deps"
mkdir -p "$repo_root/deps"
for wheel in "$work_dir/arm64-wheels"/*.whl; do
    python -m zipfile -e "$wheel" "$repo_root/deps"
done
rm -rf "$repo_root/deps"/*.dist-info
cp .artifactignore "$repo_root/deps"

# Include generated package data and the legacy worker's vendored protobuf.
if [[ $version_minor -lt 13 ]]; then
    cp -r azure_functions_worker/protos "$repo_root/deps/azure_functions_worker/"
    mkdir -p "$repo_root/deps/azure_functions_worker/_vendored"
    cp -r azure_functions_worker/_vendored/. "$repo_root/deps/azure_functions_worker/_vendored/"
else
    cp -r proxy_worker/protos "$repo_root/deps/proxy_worker/"
fi

echo "Complete ARM64 worker payload built for Python $PYTHON_VERSION"