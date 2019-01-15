#!/bin/bash

set -e -x
      
python -m pip install -U -e .[dev]
python setup.py webhost