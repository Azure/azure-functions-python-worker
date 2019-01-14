#!/bin/bash

set -e -x
export PATH="$(pwd)/.dotnet:${PATH}"
export AzureWebJobsStorage=$LINUXSTORAGECONNECTIONSTRING
export AzureWebJobsCosmosDBConnectionString=$LINUXCOSMOSDBCONNECTIONSTRING
export AzureWebJobsEventHubConnectionString=$LINUXEVENTHUBCONNECTIONSTRING
export AzureWebJobsServiceBusConnectionString=$LINUXSERVICEBUSCONNECTIONSTRING
python setup.py test