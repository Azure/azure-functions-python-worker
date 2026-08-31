# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Build the R2P2 release artifact tree for packaging (Windows X64 / Arm64).
#
# Windows analogue of r2p2_deps.sh. Unlike the Python workers (pure pip
# installs), the R2P2 is a compiled binary that embeds CPython via PyO3. This
# script:
#   1. compiles the release binary (r2p2.exe) against the target interpreter,
#   2. installs the v2 + v1 runtimes + azure-functions into $DEPS,
#   3. overlays native_invocation.py / executor.py (native + logging path),
#   4. stages the binary and the bridge.
#
# The resulting $BUILD_SOURCESDIRECTORY\deps tree mirrors the runtime worker
# directory and is copied into the NuGet under tools\<version>\WINDOWS\<Arch>.
#
# Arg 1: python version (e.g. 3.15). The Rust binary is linked to exactly one
# CPython ABI, so this must match the interpreter the worker will run against.
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonVersion
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true

Set-Location $env:BUILD_SOURCESDIRECTORY
$DEPS = Join-Path $env:BUILD_SOURCESDIRECTORY 'deps'
$WORKER = Join-Path $env:BUILD_SOURCESDIRECTORY 'workers\r2p2'

python -m venv .env
& .\.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "setuptools>=62,<82.0"

# --- Rust toolchain -------------------------------------------------------
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    $arch = if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64') { 'aarch64' } else { 'x86_64' }
    Invoke-WebRequest "https://win.rustup.rs/$arch" -OutFile rustup-init.exe
    ./rustup-init.exe -y --profile minimal --default-toolchain stable
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
}
rustc --version
cargo --version

# --- Compile the release binary against the target interpreter ------------
# PyO3 (auto-initialize) links libpython; pin PYO3_PYTHON to the venv python.
$env:PYO3_PYTHON = (Get-Command python).Source
Push-Location $WORKER
cargo build --release --locked
Pop-Location

# --- v2 + v1 runtimes + app SDK into the deps tree ------------------------
python -m pip install ./runtimes/v2 ./runtimes/v1 azure-functions `
    --no-compile --target $DEPS

# --- Stage the runtime worker-directory layout ----------------------------
Copy-Item "$WORKER\target\release\r2p2.exe" "$DEPS\r2p2.exe" -Force
if (Test-Path "$DEPS\bridge") { Remove-Item "$DEPS\bridge" -Recurse -Force }
Copy-Item "$WORKER\bridge" "$DEPS\bridge" -Recurse -Force

# Native (protobuf-free) invocation entry + executor overlay (invocation_id
# correlation for user logs) for BOTH runtimes. Additive: only imports stable
# public helpers. The bridge selects v2 or v1 per programming model.
Copy-Item 'runtimes\v2\azure_functions_runtime\native_invocation.py' `
    "$DEPS\azure_functions_runtime\native_invocation.py" -Force
Copy-Item 'runtimes\v2\azure_functions_runtime\utils\executor.py' `
    "$DEPS\azure_functions_runtime\utils\executor.py" -Force
Copy-Item 'runtimes\v1\azure_functions_runtime_v1\native_invocation.py' `
    "$DEPS\azure_functions_runtime_v1\native_invocation.py" -Force
Copy-Item 'runtimes\v1\azure_functions_runtime_v1\utils\executor.py' `
    "$DEPS\azure_functions_runtime_v1\utils\executor.py" -Force

Copy-Item 'workers\.artifactignore' $DEPS -Force -ErrorAction SilentlyContinue

Write-Host "R2P2 artifact staged under: $DEPS"
Get-ChildItem $DEPS | Select-Object -ExpandProperty Name
