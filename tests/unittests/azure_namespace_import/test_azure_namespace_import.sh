#! /bin/bash

# $1 controls whether we allow reload module ("true" or "false")

SCRIPT_DIR="$(dirname $0)"
export PYTHONPATH="$SCRIPT_DIR/namespace_location_a:$SCRIPT_DIR/namespace_location_b"

python -m $SCRIPT_DIR/azure_namespace_import.py $1

unset PYTHONPATH