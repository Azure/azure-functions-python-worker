#! /bin/bash

# $2 is sys.path from caller
export PYTHONPATH="test_module_dir:$2"
SCRIPT_DIR="$(dirname $0)"

python $SCRIPT_DIR/path_import.py $1

unset PYTHONPATH