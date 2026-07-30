#!/bin/bash
set -e

export PIP_INDEX_URL="https://pkgs.dev.azure.com/azfunc/public/_packaging/upstream-public/pypi/simple/"
export UV_INDEX_URL="$PIP_INDEX_URL"
export UV_KEYRING_PROVIDER=subprocess
echo "Using index: $PIP_INDEX_URL"

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonExtensionArtifact/$3
$UV_PIP --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]

$UV_PIP -U -e workers/[dev]