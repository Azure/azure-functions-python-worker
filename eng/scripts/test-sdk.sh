#!/bin/bash
set -e

python -m pip install --upgrade pip
python -m pip install uv

UV_PIP="python -m uv pip install --system"

$UV_PIP "setuptools>=62,<82.0"
$UV_PIP -e $1/PythonSdkArtifact
$UV_PIP -e workers/[dev]

$UV_PIP -U --prerelease=allow -e workers/[test-http-v2]
$UV_PIP -U --prerelease=allow -e workers/[test-deferred-bindings]