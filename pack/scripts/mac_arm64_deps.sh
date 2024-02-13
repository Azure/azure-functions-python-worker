#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip==23.0
python -m pip install --upgrade setuptools

python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"