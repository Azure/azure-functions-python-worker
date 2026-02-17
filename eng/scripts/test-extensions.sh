#!/bin/bash

python -m pip install --upgrade pip

python -m pip install "setuptools>=62,<82.0"
python -m pip install -e $1/PythonExtensionArtifact/$3
python -m pip install --pre -e workers/[test-http-v2]
python -m pip install --pre -U -e workers/[test-deferred-bindings]

python -m pip install -U -e workers/[dev]