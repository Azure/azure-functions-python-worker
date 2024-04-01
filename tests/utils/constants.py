# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import pathlib

# Extensions necessary for non-core bindings.
EXTENSIONS_CSPROJ_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
   <Project Sdk="Microsoft.NET.Sdk">
      <PropertyGroup>
      <TargetFramework>net8.0</TargetFramework>
      <WarningsAsErrors></WarningsAsErrors>
      <DefaultItemExcludes>**</DefaultItemExcludes>
   </PropertyGroup>
   <ItemGroup>
      <PackageReference Include="Azure.Messaging.EventHubs"
        Version="5.11.1" />
      <PackageReference Include="Azure.Messaging.EventGrid"
        Version="4.23.0" />
      <PackageReference Include="Microsoft.NET.Sdk.Functions"
        Version="4.3.0" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.CosmosDB"
        Version="4.5.0" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.EventHubs"
        Version="6.2.0" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.EventGrid"
        Version="3.3.1" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.Storage"
        Version="5.2.2" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.ServiceBus"
        Version="5.14.0" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.Sql"
        Version="3.0.534" />
      <PackageReference
        Include="Microsoft.Azure.WebJobs.Script.ExtensionsMetadataGenerator"
        Version="4.0.1" />
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.DurableTask"
        Version="2.13.2" />
      <PackageReference Include="System.Drawing.Common"
        Version="4.7.3" />
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
