#!/bin/bash

wget -q https://packages.microsoft.com/config/ubuntu/16.04/packages-microsoft-prod.deb \
&& sudo dpkg -i packages-microsoft-prod.deb \
&& sudo apt-get update \
&& sudo apt-get install -y azure-functions-core-tools
