#!/bin/bash

set -e -x

python --version

pip install -U -e .[dev]
python setup.py webhost
