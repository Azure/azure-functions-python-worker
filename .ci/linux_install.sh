#!/bin/bash

set -e -x

mkdir .dotnet
wget https://raw.githubusercontent.com/dotnet/cli/80d542b8f4eff847a0f72dc8f2c2a29851272778/scripts/obtain/dotnet-install.sh
chmod +x dotnet-install.sh
./dotnet-install.sh --version ${DOTNET_VERSION} --install-dir .dotnet

.dotnet/dotnet --info
python --version
