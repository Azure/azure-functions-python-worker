#!/bin/bash

set -e -x
      
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple -U -e .[dev]
python setup.py webhost