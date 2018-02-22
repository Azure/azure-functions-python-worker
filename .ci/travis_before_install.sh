#!/bin/bash

set -e -x

git clone --depth 1 https://github.com/yyuu/pyenv.git ~/.pyenv
PYENV_ROOT="$HOME/.pyenv"
PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

if ! (pyenv versions | grep "${PYTHON_VERSION}$"); then
    pyenv install ${PYTHON_VERSION}
fi
pyenv global ${PYTHON_VERSION}
pyenv rehash
