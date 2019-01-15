#!/bin/bash

sudo add-apt-repository -y \
'deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-xenial-prod xenial main' \
&& sudo apt-get update \
&& sudo apt-get install -y \
azure-functions-core-tools