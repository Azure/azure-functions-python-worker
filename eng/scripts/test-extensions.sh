#!/bin/bash

cd workers
python -m pip install --upgrade pip
python -m pip install uv
if [[ $2 != "3.7" ]]; then
    python -m uv pip install -e $1/PythonExtensionArtifact/$3
    python -m uv pip install --pre -e workers/[test-http-v2]
fi
if [[ $2 != "3.7" && $2 != "3.8" ]]; then
    python -m uv pip install -e $1/PythonExtensionArtifact/$3
    python -m uv pip install --pre -U -e workers/[test-deferred-bindings]
fi

python -m uv pip install -U -e workers/[dev]