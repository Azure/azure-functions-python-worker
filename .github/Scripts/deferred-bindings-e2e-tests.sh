#!/usr/bin/env bash
python -m pytest -q -n auto --dist loadfile --reruns 4 --cov=./azure_functions_worker --cov-report xml --cov-branch --cov-append tests/extension_tests/deferred_bindings_tests