#!/bin/bash

set -e -x
export AzureWebJobsStorage=$LINUXSTORAGECONNECTIONSTRING
export AzureWebJobsCosmosDBConnectionString=$LINUXCOSMOSDBCONNECTIONSTRING
export AzureWebJobsEventHubConnectionString=$LINUXEVENTHUBCONNECTIONSTRING
export AzureWebJobsServiceBusConnectionString=$LINUXSERVICEBUSCONNECTIONSTRING
export AzureWebJobsSqlConnectionString=$LINUXSQLCONNECTIONSTRING
export AzureWebJobsEventGridTopicUri=$LINUXEVENTGRIDTOPICURI
export AzureWebJobsEventGridConnectionKey=$LINUXEVENTGRIDTOPICCONNECTIONKEY

python -m pytest -n auto --dist loadfile --reruns 4 -vv tests/endtoend
