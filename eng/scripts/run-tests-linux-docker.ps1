# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Reproduces the runtimes/v2 (or v1) Linux CI test run locally in a
# python:<version>-bookworm container. Mirrors the official pipeline
# command from eng/templates/jobs/ci-library-unit-tests.yml so failures
# match CI.
#
# Usage from anywhere:
#
#   pwsh -File eng/scripts/run-tests-linux-docker.ps1
#   pwsh -File eng/scripts/run-tests-linux-docker.ps1 -Runtime v1
#   pwsh -File eng/scripts/run-tests-linux-docker.ps1 -PyVersion 3.14
#   pwsh -File eng/scripts/run-tests-linux-docker.ps1 `
#       -TestArgs 'tests/unittests/test_rpc_messages.py::TestGRPC::test_reload_env_message'
#   pwsh -File eng/scripts/run-tests-linux-docker.ps1 -Shell    # drop into bash
#
# Notes:
#   * Bind-mounts the current repo into the container so local edits
#     take effect immediately, no rebuild needed.
#   * Does not require Azure credentials. These unit tests do not
#     exercise Azure resources.
#   * The companion run-tests-linux-docker.sh does the actual install
#     and pytest invocation inside the container.

[CmdletBinding()]
param(
    [ValidateSet('v1', 'v2')]
    [string]$Runtime = 'v2',
    [string]$PyVersion = '3.13',
    [string]$TestArgs = 'tests/unittests',
    [string]$PytestExtra = '-v --tb=short -p no:randomly',
    [switch]$Shell
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ProjectDir = Join-Path $RepoRoot "runtimes/$Runtime"
if (-not (Test-Path $ProjectDir)) {
    throw "Project directory not found: $ProjectDir"
}

# Docker bind mounts on Windows want forward-slash paths.
$RepoMount = $RepoRoot.Replace('\', '/')
$ContainerRepo = '/work'
$ContainerProj = "$ContainerRepo/runtimes/$Runtime"
$ContainerScript = "$ContainerRepo/eng/scripts/run-tests-linux-docker.sh"

$Image = "python:$PyVersion-bookworm"
$ContainerName = "afpw-tests-$Runtime-$($PyVersion -replace '\.', '')".ToLower()

Write-Host "[Image]    $Image"          -ForegroundColor Cyan
Write-Host "[Mount]    $RepoMount -> $ContainerRepo" -ForegroundColor Cyan
Write-Host "[Project]  $ContainerProj"  -ForegroundColor Cyan
Write-Host "[Tests]    $TestArgs"       -ForegroundColor Cyan
Write-Host ""

# Best-effort cleanup of any prior container with the same name.
& docker rm -f $ContainerName 2>$null | Out-Null

$DockerArgs = @(
    'run', '--rm',
    '--name', $ContainerName,
    '-v', "${RepoMount}:${ContainerRepo}",
    '-w', $ContainerProj,
    '-e', "AFPW_PROJECT_DIR=$ContainerProj",
    '-e', "AFPW_PYTEST_EXTRA=$PytestExtra",
    '-e', "AFPW_TEST_ARGS=$TestArgs"
)

if ($Shell) {
    Write-Host "[Mode] Interactive shell (Ctrl-D to exit)" -ForegroundColor Yellow
    $DockerArgs += @('-it', $Image, 'bash', '-c',
        "bash $ContainerScript; exec bash")
} else {
    $DockerArgs += @($Image, 'bash', $ContainerScript)
}

& docker @DockerArgs
$ExitCode = $LASTEXITCODE

Write-Host ""
if ($ExitCode -eq 0) {
    Write-Host "[PASS] pytest exited 0" -ForegroundColor Green
} else {
    Write-Host "[FAIL] pytest exited $ExitCode" -ForegroundColor Red
}
exit $ExitCode
