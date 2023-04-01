#!/bin/bash

set -e -x
export AzureWebJobsStorage=$LINUXSTORAGECONNECTIONSTRING
export AzureWebJobsCosmosDBConnectionString=$LINUXCOSMOSDBCONNECTIONSTRING
export AzureWebJobsEventHubConnectionString=$LINUXEVENTHUBCONNECTIONSTRING
export AzureWebJobsServiceBusConnectionString=$LINUXSERVICEBUSCONNECTIONSTRING
export AzureWebJobsSqlConnectionString=$LINUXSQLCONNECTIONSTRING
export AzureWebJobsEventGridTopicUri=$LINUXEVENTGRIDTOPICURI
export AzureWebJobsEventGridConnectionKey=$LINUXEVENTGRIDTOPICCONNECTIONKEY

pytest -n auto --dist loadfile --reruns 4 -vv --instafail --cov=./azure_functions_worker --cov-report xml --cov-branch --cov-append tests/endtoend
