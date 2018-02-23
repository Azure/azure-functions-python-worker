#!/bin/bash

set -e -x

python --version

.ci/travis_download_webhost.sh

pip install -U -e .[dev]
