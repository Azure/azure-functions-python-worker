#!/bin/bash

python -m venv .env
source .env/bin/activate

python -m pip install .
python setup.py build