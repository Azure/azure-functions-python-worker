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
    python -m pip install --pre -U azurefunctions-extensions-bindings-blob==1.1.1
    python -m pip install --pre -U azurefunctions-extensions-bindings-eventhub==1.0.0b1
    python -m pip install --pre -U --no-deps azurefunctions-extensions-bindings-servicebus==1.0.0b2


fi
