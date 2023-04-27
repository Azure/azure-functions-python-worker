#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip setuptools wheel

python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"