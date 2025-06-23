#!/bin/bash

cd workers
python -m pip install --upgrade pip
python -m pip install -U azure-functions --pre
python -m pip install -U -e .[dev]

if [[ $1 != "3.7" ]]; then
    python -m pip install --pre -U -e .[test-http-v2]
fi
if [[ $1 != "3.7" && $1 != "3.8" ]]; then
    python -m pip install --pre -U -e .[test-deferred-bindings]
fi

pip install grpcio==1.35.0 protobuf==3.9.0 --only-binary=:all: -t tests/endtoend/dependency_isolation_functions/.python_packages_grpc_protobuf/lib/site-packages
