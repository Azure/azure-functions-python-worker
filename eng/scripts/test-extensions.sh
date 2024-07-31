#!/bin/bash

python -m pip install --upgrade pip
if [[ $2 != "3.7" ]]; then
    python -m pip install -e $1/PythonExtensionArtifact
    python -m pip install --pre -U -e .[test-http-v2]
fi
if [[ $2 != "3.7" && $2 != "3.8" ]]; then
    python -m pip install -e $1/PythonExtensionArtifact
    python -m pip install --pre -U -e .[test-deferred-bindings]
fi

python -m pip install -U -e .[dev]