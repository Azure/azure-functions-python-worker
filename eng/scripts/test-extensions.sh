#!/bin/bash
set -e

export UV_INDEX_URL="https://pkgs.dev.azure.com/azfunc/internal/_packaging/PythonWorker_Internal_PublicPackages/pypi/simple/"
export UV_KEYRING_PROVIDER=subprocess
echo "UV index: $UV_INDEX_URL"

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonExtensionArtifact/$3
$UV_PIP --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]

$UV_PIP -U -e workers/[dev]