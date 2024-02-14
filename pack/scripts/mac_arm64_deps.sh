#!/bin/bash

python -m venv .env
source .env/bin/activate

PYTHON_VERSION=$(python --version 2>&1)

if [[ $PYTHON_VERSION == *"3.12"* ]]; then
  python -m ensurepip --upgrade
fi

python -m pip install --upgrade pip==23.0

python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"