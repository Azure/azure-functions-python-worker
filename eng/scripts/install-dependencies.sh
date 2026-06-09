#!/bin/bash
set -e

# Install uv for faster dependency resolution / installation.
python -m pip install --upgrade pip
python -m pip install uv

# Use uv as a drop-in replacement for pip. `--system` installs into the active
# Python environment (the agent's Python), matching previous `pip install` behavior.
UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e runtimes/v2
$UV_PIP -e runtimes/v1
$UV_PIP -U --prerelease=allow azure-functions
$UV_PIP -U --prerelease=allow -e $2/[dev]

$UV_PIP -U --prerelease=allow -e $2/[test-http-v2]
$UV_PIP -U --prerelease=allow -e $2/[test-deferred-bindings]

SERVICEBUS_DIR="./servicebus_dir"
python -m uv pip install --prerelease=allow -U --target "$SERVICEBUS_DIR" azurefunctions-extensions-bindings-servicebus==1.0.0b2
python -c "import sys; sys.path.insert(0, '$SERVICEBUS_DIR'); import azurefunctions.extensions.bindings.servicebus as sb; print('servicebus version:', sb.__version__)"
