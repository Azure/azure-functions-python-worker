#! /bin/bash

# $2 is sys.path from caller
export PYTHONPATH="test_module_dir:$2"
SCRIPT_DIR="$(dirname $0)"

if [ "$1" = "fail" ]
    then
        python $SCRIPT_DIR/path_import.py 'fail'
else
    python $SCRIPT_DIR/path_import.py 'success'
fi

unset PYTHONPATH