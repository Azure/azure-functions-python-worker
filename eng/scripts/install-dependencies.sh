#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -e runtimes/v2
python -m pip install -e runtimes/v1
python -m pip install -U azure-functions --pre

# uv is only available on Python 3.8+
if [[ $2 != "3.7" ]]; then
    python -m pip install uv
    python -m uv pip install -U -e $2/[dev]
fi

# Install normal way for 3.7
if [[ $2 == "3.7" ]]; then
    python -m pip install -U -e $2/[dev]
fi

if [[ $1 != "3.7" ]]; then
    python -m pip install --pre -U -e $2/[test-http-v2]
fi
if [[ $1 != "3.7" && $1 != "3.8" ]]; then
    python -m pip install --pre -U -e $2/[test-deferred-bindings]
fi
