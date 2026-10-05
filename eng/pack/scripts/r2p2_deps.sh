#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Build the R2P2 release artifact tree for packaging (Linux/X64 and Linux/Arm64).
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
# tools/<version>/LINUX/<architecture>.
#
# Arg 1: python version (e.g. 3.15). The Rust binary is linked to exactly one
# CPython ABI, so this must match the interpreter the worker will run against.
# Arg 2: target architecture (x64 or arm64).
set -euo pipefail

PYTHON_VERSION="${1:?usage: r2p2_deps.sh <python-version> [x64|arm64]}"
ARCHITECTURE="${2:-x64}"
DEPS="$BUILD_SOURCESDIRECTORY/deps"
WORKER="$BUILD_SOURCESDIRECTORY/workers/r2p2"

if [[ "$ARCHITECTURE" != "x64" && "$ARCHITECTURE" != "arm64" ]]; then
   echo "Unsupported architecture: $ARCHITECTURE" >&2
   exit 1
fi

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
CARGO_ARGS=(build --release --locked)
BINARY_PATH="$WORKER/target/release/r2p2"
if [[ "$ARCHITECTURE" == "arm64" ]]; then
   RUST_TARGET="aarch64-unknown-linux-gnu"
   rustup target add "$RUST_TARGET"
   sudo apt-get update
   sudo apt-get install -y gcc-aarch64-linux-gnu g++-aarch64-linux-gnu make pkg-config

   if [[ "$PYTHON_VERSION" =~ ^([0-9]+\.[0-9]+\.[0-9]+)-(a|b|rc)\.?([0-9]+)$ ]]; then
      PYTHON_BASE_VERSION="${BASH_REMATCH[1]}"
      PYTHON_ARTIFACT_VERSION="${BASH_REMATCH[1]}${BASH_REMATCH[2]}${BASH_REMATCH[3]}"
   elif [[ "$PYTHON_VERSION" =~ ^([0-9]+\.[0-9]+\.[0-9]+)$ ]]; then
      PYTHON_BASE_VERSION="${BASH_REMATCH[1]}"
      PYTHON_ARTIFACT_VERSION="${BASH_REMATCH[1]}"
   else
      echo "Unsupported Python version format: $PYTHON_VERSION" >&2
      exit 1
   fi
   if [[ "$PYTHON_BASE_VERSION" =~ ^([0-9]+)\.([0-9]+)\. ]]; then
      PYTHON_MAJOR_MINOR="${BASH_REMATCH[1]}.${BASH_REMATCH[2]}"
   else
      echo "Unable to determine Python major/minor from $PYTHON_VERSION" >&2
      exit 1
   fi

   PYTHON_CROSS_ROOT="$AGENT_TEMPDIRECTORY/cpython-$PYTHON_ARTIFACT_VERSION-arm64"
   PYTHON_SOURCE="$PYTHON_CROSS_ROOT/source"
   PYTHON_BUILD="$PYTHON_CROSS_ROOT/build"
   PYTHON_SDK="$PYTHON_CROSS_ROOT/sdk"
   PYTHON_ARCHIVE="$AGENT_TEMPDIRECTORY/Python-$PYTHON_ARTIFACT_VERSION.tgz"
   curl -fsSL "https://www.python.org/ftp/python/$PYTHON_BASE_VERSION/Python-$PYTHON_ARTIFACT_VERSION.tgz" \
      -o "$PYTHON_ARCHIVE"
   mkdir -p "$PYTHON_SOURCE" "$PYTHON_BUILD" "$PYTHON_SDK/include/python$PYTHON_MAJOR_MINOR" "$PYTHON_SDK/lib"
   tar -xzf "$PYTHON_ARCHIVE" -C "$PYTHON_SOURCE" --strip-components=1

   cat > "$PYTHON_BUILD/config.site" <<'EOF'
ac_cv_file__dev_ptmx=yes
ac_cv_file__dev_ptc=no
EOF
   (
      cd "$PYTHON_BUILD"
      CONFIG_SITE="$PYTHON_BUILD/config.site" \
      CC=aarch64-linux-gnu-gcc \
      CXX=aarch64-linux-gnu-g++ \
      "$PYTHON_SOURCE/configure" \
         --build="$($PYTHON_SOURCE/config.guess)" \
         --host=aarch64-linux-gnu \
         --with-build-python="$(command -v python)" \
         --enable-shared \
         --without-ensurepip \
         --disable-test-modules
      make -j"$(nproc)"
   )

   cp -a "$PYTHON_SOURCE/Include/." "$PYTHON_SDK/include/python$PYTHON_MAJOR_MINOR/"
   cp "$PYTHON_BUILD/pyconfig.h" "$PYTHON_SDK/include/python$PYTHON_MAJOR_MINOR/"
   cp -a "$PYTHON_BUILD"/libpython"$PYTHON_MAJOR_MINOR".so* "$PYTHON_SDK/lib/"
   SYSCONFIG_DATA="$(find "$PYTHON_BUILD" -name '_sysconfigdata*.py' -print -quit)"
   if [[ -z "$SYSCONFIG_DATA" ]]; then
      echo "The ARM64 CPython build did not produce _sysconfigdata." >&2
      exit 1
   fi
   cp "$SYSCONFIG_DATA" "$PYTHON_SDK/lib/"

   export PYO3_CROSS=1
   export PYO3_CROSS_LIB_DIR="$PYTHON_SDK/lib"
   export PYO3_CROSS_PYTHON_VERSION="$PYTHON_MAJOR_MINOR"
   export PYO3_CROSS_PYTHON_IMPLEMENTATION=CPython
   export CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc
   CARGO_ARGS+=(--target "$RUST_TARGET")
   BINARY_PATH="$WORKER/target/$RUST_TARGET/release/r2p2"
else
   export PYO3_PYTHON="$(command -v python)"
   PY_LIBDIR="$(python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
   export LD_LIBRARY_PATH="${PY_LIBDIR}:${LD_LIBRARY_PATH:-}"
fi
( cd "$WORKER" && cargo "${CARGO_ARGS[@]}" )

# --- v2 + v1 runtimes + app SDK into the deps tree ------------------------
python -m pip install ./runtimes/v2 ./runtimes/v1 azure-functions \
    --no-compile --target "$DEPS"

# --- Stage the runtime worker-directory layout ----------------------------
cp "$BINARY_PATH" "$DEPS/r2p2"
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
