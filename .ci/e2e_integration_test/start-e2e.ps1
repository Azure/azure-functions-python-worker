#
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#

# Python worker E2E integration test
# The E2E integration test will test the worker against a prerelease version of core tools
$FUNC_RUNTIME_VERSION = '3'
$FUNC_RUNTIME_LANGUAGE = 'python'
$AZURE_FUNCTIONS_ENVIRONMENT = "development"
$PYAZURE_WEBHOST_DEBUG = "true"
$PYAZURE_INTEGRATION_TEST = "true"

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

function get_func_execuable_path($path) {
    $exe_name = "func"
    if ($IsWindows) {
        $exe_name = "func.exe"
    }
    return Join-Path $path $exe_name
}

$FUNC_CLI_DIRECTORY = Join-Path $PSScriptRoot 'Azure.Functions.Cli'
$FUNC_CLI_DIRECTORY_EXIST = Test-Path -Path $FUNC_CLI_DIRECTORY -PathType Container
if ($FUNC_CLI_DIRECTORY_EXIST) {
    Write-Host 'Deleting Functions Core Tools...'
    Remove-Item -Force "$FUNC_CLI_DIRECTORY.zip" -ErrorAction Ignore
    Remove-Item -Recurse -Force $FUNC_CLI_DIRECTORY -ErrorAction Ignore
}

$version = Invoke-RestMethod -Uri "$(get_core_tools_version_url)"
Write-Host "Downloading Functions Core Tools $version..."

$output = "$FUNC_CLI_DIRECTORY.zip"
Invoke-RestMethod -Uri "$(get_core_tool_download_url)" -OutFile $output

Write-Host 'Extracting Functions Core Tools...'
Expand-Archive $output -DestinationPath $FUNC_CLI_DIRECTORY -InformationAction SilentlyContinue

Write-Host "Starting Functions Host..."
$env:FUNCTIONS_WORKER_RUNTIME = $FUNC_RUNTIME_LANGUAGE
$env:FUNCTIONS_WORKER_RUNTIME_VERSION = $env:PythonVersion
$env:AZURE_FUNCTIONS_ENVIRONMENT = $AZURE_FUNCTIONS_ENVIRONMENT
$env:PYAZURE_WEBHOST_DEBUG = $PYAZURE_WEBHOST_DEBUG
$env:PYAZURE_INTEGRATION_TEST = $PYAZURE_INTEGRATION_TEST

$env:Path = "$env:Path$([System.IO.Path]::PathSeparator)$FUNC_CLI_DIRECTORY"
$funcExePath = $(get_func_execuable_path $FUNC_CLI_DIRECTORY)

if ($IsMacOS -or $IsLinux) {
    chmod -R 755 $FUNC_CLI_DIRECTORY
}
Write-Host "Function Exe Path: $funcExePath"

Set-Location $env:BUILD_SOURCESDIRECTORY
Write-Host "Set-Location: $env:BUILD_SOURCESDIRECTORY"

Write-Host "Preparing E2E integration tests..." -ForegroundColor Green
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
python -m pip install -U pip
pip install -e .[dev]
python setup.py build
python setup.py extension
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green

Write-Host "Running E2E integration tests..." -ForegroundColor Green
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
$env:CORE_TOOLS_EXE_PATH = "$funcExePath"
pytest --junitxml=e2e-integration-test-report.xml --cov=./azure_functions_worker --cov-branch --cov-append tests/endtoend --cov-report xml --cov-report html
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
