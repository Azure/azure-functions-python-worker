#!/bin/bash

python -m venv .env
source .env/bin/activate
python -m pip install --upgrade pip

#python -m pip install .

python -m pip install . \
       --platform manylinux_2_17_aarch64 \
       --platform macosx_10_9_universal2  \
       --only-binary=:all:  \
       --target "$BUILD_SOURCESDIRECTORY/deps" \
