#!/bin/bash
set -e

python -m pip install --upgrade pip
python -m pip install uv

# PipAuthenticate@1 writes the authenticated feed URL to pip's config file but
# does not expose it as a plain env var (the URL contains a PAT token). uv does
# not read pip's config, so extract the URL here and forward it via UV_INDEX_URL.
_uv_index=$(python -m pip config get global.index-url 2>/dev/null || \
            python -m pip config get global.extra-index-url 2>/dev/null || true)
[ -n "$_uv_index" ] && export UV_INDEX_URL="$_uv_index"

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonExtensionArtifact/$3
$UV_PIP --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]

$UV_PIP -U -e workers/[dev]