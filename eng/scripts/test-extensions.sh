#!/bin/bash
set -e

if [ -n "${PIP_INDEX_URL:-}" ] && [ -z "${UV_DEFAULT_INDEX:-}" ]; then
  export UV_DEFAULT_INDEX="$PIP_INDEX_URL"
fi

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonExtensionArtifact/$3
$UV_PIP --prerelease=if-necessary-or-explicit -e workers/[test-http-v2]
$UV_PIP -U --prerelease=if-necessary-or-explicit -e workers/[test-deferred-bindings]

$UV_PIP -U -e workers/[dev]