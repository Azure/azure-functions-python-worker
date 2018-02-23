#!/bin/bash

set -e -x

python --version

.ci/travis_download_webhost.sh

pip install -r requirements-dev.txt
pip install -e .

python setup.py gen_grpc
