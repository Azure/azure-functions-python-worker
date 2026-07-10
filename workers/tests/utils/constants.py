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
      <PackageReference Include="Microsoft.Azure.WebJobs.Extensions.Tables"
        Version="1.2.1" />
      <PackageReference Include="System.Drawing.Common"
        Version="4.7.3" />
      <PackageReference Include="System.Text.Json"
        Version="6.0.9" />
   </ItemGroup>
</Project>
"""

NUGET_CONFIG = """\
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
   <packageSources>
      <add key="nuget.org"
        value="https://www.nuget.org/api/v2/" />
      <add key="azure_app_service"
        value="https://www.myget.org/F/azure-appservice/api/v2" />
      <add key="azure_app_service_staging"
        value="https://www.myget.org/F/azure-appservice-staging/api/v2" />
      <add key="buildTools"
        value="https://www.myget.org/F/30de4ee06dd54956a82013fa17a3accb/" />
      <add key="AspNetVNext"
        value="https://www.myget.org/F/aspnetcore-dev/api/v3/index.json" />
   </packageSources>
</configuration>
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
DEDICATED_DOCKER_TEST = "DEDICATED_DOCKER_TEST"

# Master key used in the webhost Secrets/host.json template; required to call
# the host's protected /admin endpoints (e.g. /admin/host/status).
MASTER_KEY = "testMasterKey"

# Paths anchored on this file's location rather than on PROJECT_ROOT/TESTS_ROOT.
# The `tests.utils` package exists in multiple trees in this repo
# (workers/tests/utils and runtimes/v1/tests/utils), so PROJECT_ROOT/TESTS_ROOT
# can resolve to the wrong tree depending on sys.path ordering. These
# constants are stable and always point at the workers/ tree.
WORKERS_TESTS_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKERS_ROOT = WORKERS_TESTS_ROOT.parent
REPO_ROOT = WORKERS_ROOT.parent
FUNCTION_APP_ZIPS_DIR = (
    WORKERS_TESTS_ROOT / 'consumption_tests' / 'function_app_zips'
)
