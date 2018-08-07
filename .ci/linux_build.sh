#!/bin/bash

set -e -x

export PATH="$(pwd)/.dotnet:${PATH}"

python -m pip install -U -e .[dev]
python setup.py webhost
