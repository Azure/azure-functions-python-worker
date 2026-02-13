#!/bin/bash

python -m pip install --upgrade pip
python -m pip install -e runtimes/v2
python -m pip install -e runtimes/v1
python -m pip install -U azure-functions --pre
python -m pip install -U -e $2/[dev]

python -m pip install --pre -U -e $2/[test-http-v2]
python -m pip install --pre -U -e $2/[test-deferred-bindings]

SERVICEBUS_DIR="./servicebus_dir"
python -m pip install --pre -U --target "$SERVICEBUS_DIR" azurefunctions-extensions-bindings-servicebus==1.0.0b2
python -c "import sys; sys.path.insert(0, '$SERVICEBUS_DIR'); import azurefunctions.extensions.bindings.servicebus as sb; print('servicebus version:', sb.__version__)"

# Install grpcio and grpcio-tools for Python versions under 3.12
PYTHON_VERSION=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$(python -c "import sys; print(int(sys.version_info.major == 3 and sys.version_info.minor <= 12))")" -eq 1 ]; then
    echo "Python version $PYTHON_VERSION detected. Force installing grpcio and grpcio-tools ~=1.59.0"
    python -m pip install "grpcio~=1.59.0" "grpcio-tools~=1.59.0"
else
    echo "Python version $PYTHON_VERSION detected. Skipping forced grpcio installation for versions 3.12+"
fi