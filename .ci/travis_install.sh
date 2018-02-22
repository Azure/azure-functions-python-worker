#!/bin/bash

set -e -x

dotnet --version

PYENV_ROOT="$HOME/.pyenv"
PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
pyenv global ${PYTHON_VERSION}

python --version

.ci/download_webhost.sh

pip install -r requirements-dev.txt
pip install -e .

python setup.py gen_grpc
