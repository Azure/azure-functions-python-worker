#!/bin/bash
set -e

# Forward the PipAuthenticate-supplied feed URL to uv. PipAuthenticate@1 sets
# PIP_EXTRA_INDEX_URL so that pip uses the internal feed, but uv does not read
# pip's config or environment variables. Setting UV_INDEX_URL makes uv use the
# internal feed as its primary index instead of going directly to pypi.org.
if [ -n "${PIP_EXTRA_INDEX_URL:-}" ]; then
    export UV_INDEX_URL="$PIP_EXTRA_INDEX_URL"
fi

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonSdkArtifact
$UV_PIP -e workers/[dev]

$UV_PIP -U --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]