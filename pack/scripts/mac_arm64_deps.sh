#!/bin/bash

python -m venv .env
source .env/bin/activate

PYTHON_VERSION=$(python --version 2>&1)
echo "Python Version: $PYTHON_VERSION"

if [[ $PYTHON_VERSION == *"3.12"* ]]; then
  echo "Upgrading ensurepip"
  python -m ensurepip --upgrade
  pip install --upgrade setuptools
else
  python -m pip install --upgrade pip==23.0
fi

python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"