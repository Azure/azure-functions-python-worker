#!/bin/bash
set -e

# Forward PipAuthenticate's index URL to uv, which does not read pip's config.
if [ -n "${PIP_INDEX_URL:-}" ] && [ -z "${UV_DEFAULT_INDEX:-}" ]; then
  export UV_DEFAULT_INDEX="$PIP_INDEX_URL"
fi

# Install uv for faster dependency resolution / installation.
python -m pip install --upgrade pip
python -m pip install uv

# Use uv as a drop-in replacement for pip. `--system` installs into the active
# Python environment (the agent's Python), matching previous `pip install` behavior.
UV_PIP="python -m uv pip install --system"

# Setuptools is needed up front for editable installs of legacy packages.
$UV_PIP "setuptools>=62,<82.0"

# runtimes/v1 and runtimes/v2 require Python >= 3.13. Old pip would silently
# install them on lower versions; uv (correctly) refuses, so install them
# conditionally. They are only consumed by proxy_worker (Python >= 3.13).
PY_VER="$1"
PY_MINOR="${PY_VER#*.}"
EXTRA_ARGS=()
if [ "${PY_MINOR:-0}" -ge 13 ]; then
    EXTRA_ARGS+=(-e runtimes/v2 -e runtimes/v1)
fi

# Install everything else in a single uv invocation so the resolver runs once
# and all wheels are downloaded in parallel.
$UV_PIP -U --prerelease=if-necessary-or-explicit \
    azure-functions \
    -e "$2/[dev]" \
    -e "$2/[test-http-v2]" \
    -e "$2/[test-deferred-bindings]" \
    "${EXTRA_ARGS[@]}"

# The servicebus binding extension depends on uamqp, which is deprecated and
# ships no wheels for Python 3.14 (source builds fail). Install it only on
# Python < 3.14, mirroring the eventhub binding gate in pyproject.toml.
if [ "${PY_MINOR:-0}" -lt 14 ]; then
    SERVICEBUS_DIR="./servicebus_dir"
    python -m uv pip install --prerelease=allow -U --target "$SERVICEBUS_DIR" azurefunctions-extensions-bindings-servicebus==1.0.0b2
    python -c "import sys; sys.path.insert(0, '$SERVICEBUS_DIR'); import azurefunctions.extensions.bindings.servicebus as sb; print('servicebus version:', sb.__version__)"
else
    echo "Skipping servicebus binding extension on Python $PY_VER (uamqp has no 3.14 wheels)."
fi
