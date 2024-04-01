# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib

# Extensions necessary for non-core bindings.
EXTENSIONS_CSPROJ_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
   <Project Sdk="Microsoft.NET.Sdk">
      <PropertyGroup>
      <TargetFramework>net8.0</TargetFramework>
      <AzureFunctionsVersion>v4</AzureFunctionsVersion>
   </PropertyGroup>
   <ItemGroup>
      <PackageReference Include="Microsoft.NET.Sdk.Functions"
        Version="4.3.0" />
   </ItemGroup>
</Project>
"""


# PROJECT_ROOT refers to the path to azure-functions-python-worker
# TODO: Find root folder without .parent
PROJECT_ROOT = pathlib.Path(__file__).parent.parent.parent
TESTS_ROOT = PROJECT_ROOT / 'tests'
WORKER_CONFIG = PROJECT_ROOT / '.testconfig'

# E2E Integration Flags and Configurations
PYAZURE_INTEGRATION_TEST = "PYAZURE_INTEGRATION_TEST"
PYAZURE_WORKER_DIR = "PYAZURE_WORKER_DIR"

# Debug Flags
PYAZURE_WEBHOST_DEBUG = "PYAZURE_WEBHOST_DEBUG"
ARCHIVE_WEBHOST_LOGS = "ARCHIVE_WEBHOST_LOGS"

# CI test constants
CONSUMPTION_DOCKER_TEST = "CONSUMPTION_DOCKER_TEST"
DEDICATED_DOCKER_TEST = "DEDICATED_DOCKER_TEST"
