#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -U azure-functions --pre
python -m pip install -U -e .[dev]

python -m pip install --pre -U -e .[test-http-v2]
python -m pip install --pre -U -e .[test-deferred-bindings]