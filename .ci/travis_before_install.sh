#!/bin/bash

set -e -x

sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-trusty-prod trusty main" > /etc/apt/sources.list.d/dotnetdev.list'
sudo apt-get update

sudo apt-get install dotnet-sdk-2.1.4 -y --allow-unauthenticated

dotnet --version
