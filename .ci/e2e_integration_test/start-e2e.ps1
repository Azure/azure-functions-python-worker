#
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project root for full license information.
#

# Python worker E2E integration test
# The E2E integration test will test the worker against a prerelease version of core tools.
# It runs against every Core Tools major version listed in $FUNC_RUNTIME_VERSIONS (default: v4 and v5).
# Override by setting the FUNC_RUNTIME_VERSIONS environment variable to a comma-separated list, e.g. "4,5".
if ($env:FUNC_RUNTIME_VERSIONS) {
    $FUNC_RUNTIME_VERSIONS = $env:FUNC_RUNTIME_VERSIONS -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ }
} else {
    $FUNC_RUNTIME_VERSIONS = @('4', '5')
}
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

function get_core_tool_download_url($runtimeVersion) {
    $os = get_os
    $arch = get_architecture
    return "https://functionsintegclibuilds.blob.core.windows.net/builds/$runtimeVersion/latest/Azure.Functions.Cli.$os-$arch.zip"
}

function get_core_tools_version_url($runtimeVersion) {
    return "https://functionsintegclibuilds.blob.core.windows.net/builds/$runtimeVersion/latest/version.txt"
}

function get_func_execuable_path($path) {
    $exe_name = "func"
    if ($IsWindows) {
        $exe_name = "func.exe"
    }
    return Join-Path $path $exe_name
}

$env:FUNCTIONS_WORKER_RUNTIME = $FUNC_RUNTIME_LANGUAGE
$env:FUNCTIONS_WORKER_RUNTIME_VERSION = $env:PythonVersion
$env:AZURE_FUNCTIONS_ENVIRONMENT = $AZURE_FUNCTIONS_ENVIRONMENT
$env:PYAZURE_WEBHOST_DEBUG = $PYAZURE_WEBHOST_DEBUG
$env:PYAZURE_INTEGRATION_TEST = $PYAZURE_INTEGRATION_TEST

Set-Location $env:BUILD_SOURCESDIRECTORY
Write-Host "Set-Location: $env:BUILD_SOURCESDIRECTORY"

Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
Write-Host "Preparing E2E integration tests..." -ForegroundColor Green
Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
python -m pip install -U pip
python -m pip install -U -e workers/[dev]
cd workers/tests
python -m invoke -c test_setup build-protos
python -m invoke -c test_setup extensions

# Run the E2E integration tests once per requested Core Tools major version.
$overallExitCode = 0
foreach ($runtimeVersion in $FUNC_RUNTIME_VERSIONS) {
    Write-Host "=============================================================================`n" -ForegroundColor Cyan
    Write-Host "Core Tools v$runtimeVersion" -ForegroundColor Cyan
    Write-Host "=============================================================================`n" -ForegroundColor Cyan

    $funcCliDirectory = Join-Path $PSScriptRoot "Azure.Functions.Cli.v$runtimeVersion"
    if (Test-Path -Path $funcCliDirectory -PathType Container) {
        Write-Host "Deleting Functions Core Tools v$runtimeVersion..."
        Remove-Item -Force "$funcCliDirectory.zip" -ErrorAction Ignore
        Remove-Item -Recurse -Force $funcCliDirectory -ErrorAction Ignore
    }

    try {
        $version = Invoke-RestMethod -Uri "$(get_core_tools_version_url $runtimeVersion)"
        Write-Host "Downloading Functions Core Tools v$runtimeVersion ($version)..."

        $output = "$funcCliDirectory.zip"
        Invoke-RestMethod -Uri "$(get_core_tool_download_url $runtimeVersion)" -OutFile $output

        Write-Host "Extracting Functions Core Tools v$runtimeVersion..."
        Expand-Archive $output -DestinationPath $funcCliDirectory -InformationAction SilentlyContinue
    } catch {
        Write-Host "Failed to download/extract Functions Core Tools v$runtimeVersion. $_" -ForegroundColor Red
        $overallExitCode = 1
        continue
    }

    $funcExePath = $(get_func_execuable_path $funcCliDirectory)
    if ($IsMacOS -or $IsLinux) {
        chmod -R 755 $funcCliDirectory
    }
    $env:Path = "$env:Path$([System.IO.Path]::PathSeparator)$funcCliDirectory"
    Write-Host "Function Exe Path: $funcExePath"

    Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
    Write-Host "Running E2E integration tests against Core Tools v$runtimeVersion..." -ForegroundColor Green
    Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
    $env:CORE_TOOLS_EXE_PATH = "$funcExePath"
    python -m pytest --junitxml=e2e-integration-test-report-v$runtimeVersion.xml --reruns 4 tests/endtoend
    if ($LASTEXITCODE -ne 0) {
        Write-Host "E2E integration tests failed against Core Tools v$runtimeVersion (exit code $LASTEXITCODE)." -ForegroundColor Red
        $overallExitCode = 1
    }
    Write-Host "-----------------------------------------------------------------------------`n" -ForegroundColor Green
}

exit $overallExitCode
