#!/bin/bash

set -e -x

dotnet --version
python --version

python setup.py test
