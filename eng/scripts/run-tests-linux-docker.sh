#!/usr/bin/env bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Runs the v1/v2 runtime unit tests inside a python:<version>-bookworm
# container. Invoked by eng/scripts/run-tests-linux-docker.ps1 via
# docker run. Three env vars expected:
#   AFPW_PROJECT_DIR    e.g. /work/runtimes/v2
#   AFPW_PYTEST_EXTRA   e.g. "-v --tb=short -p no:randomly"
#   AFPW_TEST_ARGS      e.g. "tests/unittests"

set -euo pipefail

echo '== Python version =='
python --version

cd "$AFPW_PROJECT_DIR"

echo
echo '== Installing runtime from local source =='
pip install --quiet --upgrade pip
# Install the runtime in editable mode with the dev extras; fall back to
# bare install if the dev extras can't be resolved.
pip install --quiet -e '.[dev]' || pip install --quiet -e .

# Test-only deps that aren't in [dev]:
pip install --quiet \
    pytest pytest-asyncio pytest-rerunfailures pytest-instafail \
    pytest-randomly pytest-xdist pytest-cov pytest-sugar

# Deferred-bindings extras (skip on 3.14 where some wheels lag).
PYV=$(python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
if [ "$PYV" != "3.14" ]; then
    pip install --quiet azurefunctions-extensions-bindings-blob || true
    pip install --quiet azurefunctions-extensions-bindings-eventhub || true
fi

echo
echo '== Running tests =='
echo "cwd: $(pwd)"
echo "cmd: python -m pytest $AFPW_PYTEST_EXTRA $AFPW_TEST_ARGS"
echo
exec python -m pytest $AFPW_PYTEST_EXTRA $AFPW_TEST_ARGS
