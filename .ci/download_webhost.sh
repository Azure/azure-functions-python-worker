#!/bin/bash

set -e -x

if [ -e "downloads/webhost/Microsoft.Azure.WebJobs.Script.WebHost.dll" ]; then
    exit 0
fi

mkdir -p downloads/webhost
cd downloads/webhost

wget http://ci.appveyor.com/api/buildjobs/y6wonxc4o3k529s8/artifacts/Functions.Binaries.2.0.11549-alpha.zip
unzip Functions.Binaries.2.0.11549-alpha.zip || true

[ -e "Microsoft.Azure.WebJobs.Script.WebHost.dll" ]
