#! /bin/bash
set -x

# Directory name for start.sh
DIR="$(dirname $0)"

# If we're not in a virtual environment, we need to start our host
if [ -z "$VIRTUAL_ENV"]
then

# Determining the virtual environment entry point
if [ -z "$AZURE_FUNCTIONS_VIRTUAL_ENVIRONMENT"]
then
    AZURE_FUNCTIONS_VIRTUAL_ENVIRONMENT='../../worker_env/bin/activate'
fi

echo "activating virtual environment"
AZFVENV=$DIR
AZFVENV+='/'
AZFVENV+=$AZURE_FUNCTIONS_VIRTUAL_ENVIRONMENT
source $AZFVENV
fi

echo "starting the python worker"
python $DIR/worker.py $@
