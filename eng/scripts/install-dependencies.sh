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
    INSTALL_DIR="./extensions_dir"
    python -m pip install --pre -U --target "$INSTALL_DIR" "$2/[test-deferred-bindings]"
    python -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); import azurefunctions.extensions.bindings.blob as blob; print(blob.__version__)"
fi
