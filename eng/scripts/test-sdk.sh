#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -e $1/PythonSdkArtifact

# uv is only available on Python 3.8+
if [[ $2 != "3.7" ]]; then
    python -m pip install uv
    python -m uv pip install -U -e workers/[dev]
fi

# Install normal way for 3.7
if [[ $2 == "3.7" ]]; then
    python -m pip install -U -e workers/[dev]
fi

if [[ $2 != "3.7" ]]; then
    python -m pip install --pre -U -e workers/[test-http-v2]
fi
if [[ $2 != "3.7" && $2 != "3.8" ]]; then
    python -m pip install --pre -U -e workers/[test-deferred-bindings]
fi