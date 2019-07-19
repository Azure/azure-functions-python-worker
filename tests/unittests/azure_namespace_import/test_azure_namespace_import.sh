#! /bin/bash

# $1 controls whether we allow reload module ("true" or "false")
# $2 is the second azure namespace location (created in unittest)

SCRIPT_DIR="$(dirname $0)"
export PYTHONPATH="$SCRIPT_DIR/namespace_location_a:$2"

python $SCRIPT_DIR/azure_namespace_import.py $1 $2

unset PYTHONPATH