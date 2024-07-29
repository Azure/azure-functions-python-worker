#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -U azure-functions --pre
python -m pip install -U -e .[dev]

if [[ $(PYTHON_VERSION) != "3.7" ]]; then
    python -m pip install --pre -U -e .[test-http-v2]
fi
if [[ $(PYTHON_VERSION) != "3.7" && $(PYTHON_VERSION) != "3.8" ]]; then
    python -m pip install --pre -U -e .[test-deferred-bindings]
fi