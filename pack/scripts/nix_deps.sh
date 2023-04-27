#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

python -m pip install . --use-pep517

python -m pip install . --no-compile --use-pep517 --target "$BUILD_SOURCESDIRECTORY/deps"