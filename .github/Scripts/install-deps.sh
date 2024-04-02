#!/usr/bin/env bash
python -m pip install --upgrade pip
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple -U azure-functions --pre
python -m pip install -U -e .[dev]