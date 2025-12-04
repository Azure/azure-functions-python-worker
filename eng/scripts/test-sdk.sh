#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -e $1/PythonSdkArtifact
python -m pip install -e workers/[dev]

python -m pip install --pre -U -e workers/[test-http-v2]
python -m pip install --pre -U -e workers/[test-deferred-bindings]