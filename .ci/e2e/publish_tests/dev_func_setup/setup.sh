#!/usr/bin/env bash

set -e
if [[ -z "$1" ]]
then
    echo "Missing name of the directory to install func CLI"
    echo "usage ./script <directory_name>"
    exit 1
fi

if [[ -z "$2" ]]
then
    echo "Missing the URL to download functions"
fi

wget $2
echo "Retrieving func CLI version: "
curl https://functionsclibuilds.blob.core.windows.net/builds/2/latest/version.txt
echo ""
unzip *.zip -d "$1"
rm -rf *.zip
chmod a+x "$1"/func