#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

python -m pip install .

python -m pip install . --no-compile --target "$BUILD_SOURCESDIRECTORY/deps"