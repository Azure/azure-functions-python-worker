#!/usr/bin/env bash

set -e
USAGE="usage ./script <ACR_Name> <dev_image_name> <working_dir>"

if [[ -z "$1" ]]
then
    echo "Missing name of the ACR"
    echo ${USAGE}
    exit 1
fi

if [[ -z "$2" ]]
then
    echo "Missing name of the dev image to use in ACR"
    echo ${USAGE}
    exit 1
fi

if [[ -z "$3" ]]
then
    echo "Missing name of the working directory"
    echo ${USAGE}
    exit 1
fi

SCRIPT_DIR=`realpath $(dirname "${BASH_SOURCE[0]}")`

mkdir -p $3
cd $3
az acr login --name $1 --output none
git clone https://github.com/Azure/azure-functions-docker
docker build -f ./azure-functions-docker/host/2.0/stretch/amd64/python-deps.Dockerfile ./azure-functions-docker/host/2.0/stretch/amd64 -t azure-functions-python-deps-dev
# The directory to build from needs to be the amd64, because the Dockerfile copies resources
docker build --build-arg BASE_PYTHON_IMAGE=azure-functions-python-deps-dev -f ./azure-functions-docker/host/2.0/stretch/amd64/python-buildenv.Dockerfile -t azure-functions-python-dev ./azure-functions-docker/host/2.0/stretch/amd64
docker build --build-arg BASE_IMAGE=azure-functions-python-dev -f ${SCRIPT_DIR}/dev.Dockerfile ${SCRIPT_DIR}/../../../.. -t azure-functions-python-dev-updated
docker tag azure-functions-python-dev-updated $1.azurecr.io/$2
docker push $1.azurecr.io/$2
echo "New image pushed to the ACR."
echo "Starting cleanup"
cd ..
rm -r $3
echo "Completed cleanup"