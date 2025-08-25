#!/bin/bash

python -m pip install --upgrade pip
python -m pip install uv
python -m uv pip install -e runtimes/v2
python -m uv pip install -e runtimes/v1
python -m uv pip install -U azure-functions --pre
python -m uv pip install -U -e $2/[dev]

if [[ $1 != "3.7" ]]; then
    python -m uv pip install --pre -U -e $2/[test-http-v2]
fi
if [[ $1 != "3.7" && $1 != "3.8" ]]; then
    python -m uvpip install --pre -U -e $2/[test-deferred-bindings]
fi
