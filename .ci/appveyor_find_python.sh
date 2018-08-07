#!/bin/sh

for d in $(ls -d /home/appveyor/venv${PYTHON_VERSION}*/bin/ | sort -nr); do
    echo "${d}"
    exit 0
done

echo "Could not find Python version ${PYTHON_VERSION}" >&2
exit 1
