#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Build the R2P2 release artifact tree for packaging (Linux/X64).
#
# Unlike the Python workers (which are pure pip installs), the R2P2 is a
# compiled binary that embeds CPython via PyO3. This script:
#   1. compiles the release binary against the target interpreter,
#   2. installs the v2 + v1 runtimes + azure-functions into $DEPS,
#   3. overlays native_invocation.py / executor.py (the native + logging path),
#   4. stages the binary and the bridge.
#
# The resulting $BUILD_SOURCESDIRECTORY/deps tree mirrors the runtime worker
# directory produced by docker/Dockerfile and is copied into the NuGet under
# tools/<version>/LINUX/X64.
#
# Arg 1: python version (e.g. 3.15). The Rust binary is linked to exactly one
# CPython ABI, so this must match the interpreter the worker will run against.
set -euo pipefail

PYTHON_VERSION="${1:?usage: r2p2_deps.sh <python-version>}"
DEPS="$BUILD_SOURCESDIRECTORY/deps"
WORKER="$BUILD_SOURCESDIRECTORY/workers/r2p2"

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip
python -m pip install "setuptools>=62,<82.0"

# --- Rust toolchain -------------------------------------------------------
if ! command -v cargo >/dev/null 2>&1; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
        | sh -s -- -y --profile minimal --default-toolchain stable
fi
export PATH="$HOME/.cargo/bin:$PATH"
rustc --version
cargo --version

# --- Compile the release binary against the target interpreter ------------
# PyO3 (auto-initialize) links libpython; pin PYO3_PYTHON and expose LIBDIR.
export PYO3_PYTHON="$(command -v python)"
PY_LIBDIR="$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
export LD_LIBRARY_PATH="${PY_LIBDIR}:${LD_LIBRARY_PATH:-}"
( cd "$WORKER" && cargo build --release --locked )

# --- v2 + v1 runtimes + app SDK into the deps tree ------------------------
python -m pip install ./runtimes/v2 ./runtimes/v1 azure-functions \
    --no-compile --target "$DEPS"

# --- Stage the runtime worker-directory layout ----------------------------
cp "$WORKER/target/release/r2p2" "$DEPS/r2p2"
rm -rf "$DEPS/bridge"
cp -r "$WORKER/bridge" "$DEPS/bridge"

# Native (protobuf-free) invocation entry + executor overlay (invocation_id
# correlation for user logs) for BOTH runtimes. Additive: only imports stable
# public helpers. The bridge selects v2 or v1 per programming model.
cp runtimes/v2/azure_functions_runtime/native_invocation.py \
   "$DEPS/azure_functions_runtime/native_invocation.py"
cp runtimes/v2/azure_functions_runtime/utils/executor.py \
   "$DEPS/azure_functions_runtime/utils/executor.py"
cp runtimes/v1/azure_functions_runtime_v1/native_invocation.py \
   "$DEPS/azure_functions_runtime_v1/native_invocation.py"
cp runtimes/v1/azure_functions_runtime_v1/utils/executor.py \
   "$DEPS/azure_functions_runtime_v1/utils/executor.py"

cp workers/.artifactignore "$DEPS" 2>/dev/null || true

echo "R2P2 artifact staged under: $DEPS"
ls -1 "$DEPS"
