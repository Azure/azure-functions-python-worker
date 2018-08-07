#!/bin/bash

set -e -x

export PATH="$(pwd)/.dotnet:${PATH}"

python setup.py test
