#!/bin/bash

set -e -x

PYENV_ROOT="$HOME/.pyenv"
PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"
pyenv global ${PYTHON_VERSION}

dotnet --version
python --version

python setup.py test
