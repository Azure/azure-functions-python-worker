#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -e runtimes/v2
python -m pip install -e runtimes/v1
python -m pip install -U azure-functions --pre
python -m pip install -U -e $2/[dev]

if [[ $1 != "3.7" ]]; then
    python -m pip install --pre -U -e $2/[test-http-v2]
fi
if [[ $1 != "3.7" && $1 != "3.8" ]]; then
    python -m pip install --pre -U -e $2/[test-deferred-bindings]

    SERVICEBUS_DIR="./servicebus_dir"
    python -m pip install --pre -U --target "$SERVICEBUS_DIR" azurefunctions-extensions-bindings-servicebus==1.0.0b2
    python -c "import sys; sys.path.insert(0, '$SERVICEBUS_DIR'); import azurefunctions.extensions.bindings.servicebus as sb; print('servicebus version:', sb.__version__)"
fi
