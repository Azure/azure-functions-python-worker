#
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#
$FUNC_RUNTIME_VERSION = '3'
$FUNC_RUNTIME_LANGUAGE = 'python'
$PYTHON_VERSION = '3.7'
$AZURE_FUNCTIONS_ENVIRONMENT = "development"

# Speed up Invoke-RestMethod by turning off progress bar
$ProgressPreference = 'SilentlyContinue'


function get_architecture() {
    # Return "x64" or "x86"
    return [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant();
}

function get_os() {
    # Return either "win", "linux", "osx", or "unknown"
    if ($IsWindows) {
        return "win"
    } elseif ($IsLinux) {
        return "linux"
    } elseif ($IsMacOS) {
        return "osx"
    }
    return "unknown"
}

function get_core_tool_download_url() {
    $os = get_os
    $arch = get_architecture
    return "https://functionsintegclibuilds.blob.core.windows.net/builds/$FUNC_RUNTIME_VERSION/latest/Azure.Functions.Cli.$os-$arch.zip"
}

function get_core_tools_version_url() {
    return "https://functionsintegclibuilds.blob.core.windows.net/builds/$FUNC_RUNTIME_VERSION/latest/version.txt"
}

$FUNC_CLI_DIRECTORY = Join-Path $env:AGENT_TEMPDIRECTORY 'Azure.Functions.Cli'
$FUNC_CLI_DIRECTORY_EXIST = Test-Path -Path $FUNC_CLI_DIRECTORY -PathType Container
if ($FUNC_CLI_DIRECTORY_EXIST) {
    Write-Host 'Deleting Functions Core Tools...'
    Remove-Item -Force "$FUNC_CLI_DIRECTORY.zip" -ErrorAction Ignore
    Remove-Item -Recurse -Force $FUNC_CLI_DIRECTORY -ErrorAction Ignore
}

$version = Invoke-RestMethod -Uri "$(get_core_tools_version_url)"
Write-Host "Downloading Functions Core Tools $version..."

$output = "$FUNC_CLI_DIRECTORY/$FUNC_CLI_DIRECTORY.zip"
Invoke-RestMethod -Uri "$(get_core_tool_download_url)" -OutFile $output

Write-Host 'Extracting Functions Core Tools...'
Expand-Archive $output -DestinationPath $FUNC_CLI_DIRECTORY

Write-Host "Starting Functions Host..."
$env:Path = "$env:Path$([System.IO.Path]::PathSeparator)$FUNC_CLI_DIRECTORY"
$funcExePath = Join-Path $FUNC_CLI_DIRECTORY $FUNC_EXE_NAME

$env:FUNCTIONS_WORKER_RUNTIME = $FUNC_RUNTIME_LANGUAGE
$env:FUNCTIONS_WORKER_RUNTIME_VERSION = $PYTHON_VERSION
$env:AZURE_FUNCTIONS_ENVIRONMENT = $AZURE_FUNCTIONS_ENVIRONMENT

if ($IsMacOS -or $IsLinux) {
    chmod -R 777 $FUNC_CLI_DIRECTORY
}
Write-Host "Function Exe Path: $funcExePath"

Set-Location $env:BUILD_SOURCESDIRECTORY
Write-Host "Set-Location: $env:BUILD_SOURCESDIRECTORY"

Write-Host "Running E2E integration tests..." -ForegroundColor Green
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green

pip install -e .[dev]
python setup.py build
python setup.py extension

$env:CORE_TOOLS_EXE_PATH = "$funcExePath"
pytest --instafail --cov=./azure_functions_worker --cov-report xml --cov-branch --cov-append tests/endtoend

Write-Host "-----------------------------------------------------------------------------" -ForegroundColor Green