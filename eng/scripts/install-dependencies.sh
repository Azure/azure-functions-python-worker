#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -U azure-functions --pre
python -m pip install -U -e .[dev]

if [[ $1 != "3.7" ]]; then
    python -m pip install --pre -U -e .[test-http-v2]
fi
if [[ $1 != "3.7" && $1 != "3.8" ]]; then
    python -m pip install --pre -U -e .[test-deferred-bindings]
fi