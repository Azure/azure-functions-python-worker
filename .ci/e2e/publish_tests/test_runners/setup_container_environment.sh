#!/usr/bin/env bash

set -e
apt-get update
apt-get install azure-functions-core-tools jq git unzip gettext -y
curl -sSL https://get.docker.com/ | sh

# Install azure CLI
apt-get install apt-transport-https lsb-release software-properties-common dirmngr -y
AZ_REPO=$(lsb_release -cs)
echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" | tee /etc/apt/sources.list.d/azure-cli.list
apt-key --keyring /etc/apt/trusted.gpg.d/Microsoft.gpg adv --keyserver packages.microsoft.com --recv-keys BC528686B50D79E339D3721CEB3E94ADBE1229CF
apt-get update
apt-get install azure-cli -y