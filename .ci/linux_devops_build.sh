#!/bin/bash

set -e -x

python -m pip install --upgrade pip

# Install the latest Azure Functions Python Worker from test.pypi.org
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple -U -e .[dev]

# Install the latest Azure Functions Python Library from test.pypi.org
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple -U azure-functions --pre

# Download Azure Functions Host
python setup.py webhost

# Setup WebJobs Extensions
python setup.py extension