# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
#
# Build the R2P2 release artifact tree for packaging (Windows X64 / X86 / Arm64).
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
# Arg 2: target architecture (x64, x86, or arm64).
param(
    [Parameter(Mandatory = $true)]
    [string]$PythonVersion,

    [ValidateSet('x64', 'x86', 'arm64')]
    [string]$Architecture = 'x64'
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

$expectedPointerWidth = if ($Architecture -eq 'x86') { 32 } else { 64 }
$pythonPointerWidth = python -c "import struct; print(struct.calcsize('P') * 8)"
if ([int]$pythonPointerWidth -ne $expectedPointerWidth) {
    throw "Host Python for $Architecture must be $expectedPointerWidth-bit, but the selected interpreter is $pythonPointerWidth-bit."
}

# --- Rust toolchain -------------------------------------------------------
if (-not (Get-Command rustup -ErrorAction SilentlyContinue)) {
    Invoke-WebRequest 'https://win.rustup.rs/x86_64' -OutFile rustup-init.exe
    ./rustup-init.exe -y --profile minimal --default-toolchain stable
    $env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
}
$rustToolchain = if ($Architecture -eq 'x86') {
    'stable-i686-pc-windows-msvc'
} else {
    'stable-x86_64-pc-windows-msvc'
}
$rustTarget = if ($Architecture -eq 'arm64') { 'aarch64-pc-windows-msvc' } else { $null }

rustup toolchain install $rustToolchain --profile minimal
if ($rustTarget) {
    rustup target add $rustTarget --toolchain $rustToolchain
}
rustup run $rustToolchain rustc --version
rustup run $rustToolchain cargo --version

# --- Compile the release binary against the target interpreter ------------
# Native builds query the selected interpreter. The ARM64 cross-build instead
# uses the official target CPython SDK and PyO3's explicit cross configuration.
$cargoArguments = @('build', '--release', '--locked')
$binaryPath = Join-Path $WORKER 'target\release\r2p2.exe'
if ($rustTarget) {
    if ($PythonVersion -notmatch '^(?<base>\d+\.\d+\.\d+)-(?<level>a|b|rc)\.?(?<serial>\d+)$' -and
        $PythonVersion -notmatch '^(?<base>\d+\.\d+\.\d+)$') {
        throw "Unsupported Python version format for the CPython download: $PythonVersion"
    }
    $baseVersion = $Matches.base
    $artifactVersion = if ($Matches.level) {
        "$baseVersion$($Matches.level)$($Matches.serial)"
    } else {
        $baseVersion
    }
    if ($baseVersion -notmatch '^(?<major>\d+)\.(?<minor>\d+)') {
        throw "Unable to determine the Python major/minor version from $PythonVersion"
    }
    $pythonMajorMinor = "$($Matches.major).$($Matches.minor)"
    $pythonLibrary = "python$($Matches.major)$($Matches.minor).lib"
    $pythonSdk = Join-Path $env:AGENT_TEMPDIRECTORY "cpython-$artifactVersion-arm64"
    $pythonArchive = Join-Path $env:AGENT_TEMPDIRECTORY "python-$artifactVersion-arm64.zip"
    $pythonUrl = "https://www.python.org/ftp/python/$baseVersion/python-$artifactVersion-arm64.zip"

    Invoke-WebRequest $pythonUrl -OutFile $pythonArchive
    Expand-Archive $pythonArchive -DestinationPath $pythonSdk -Force
    $pythonHeader = Join-Path $pythonSdk 'include\Python.h'
    $pythonImportLibrary = Join-Path $pythonSdk "libs\$pythonLibrary"
    if (-not (Test-Path $pythonHeader) -or -not (Test-Path $pythonImportLibrary)) {
        throw "The ARM64 CPython SDK is missing $pythonHeader or $pythonImportLibrary."
    }

    $vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    $vsInstall = & $vswhere -latest -products * `
        -requires Microsoft.VisualStudio.Component.VC.Tools.ARM64 `
        -property installationPath
    if (-not $vsInstall) {
        throw 'Visual Studio ARM64 C++ cross tools are not installed.'
    }
    $devCmd = Join-Path $vsInstall 'Common7\Tools\VsDevCmd.bat'
    & $env:COMSPEC /s /c "`"$devCmd`" -no_logo -arch=arm64 -host_arch=x64 >nul && set" |
        ForEach-Object {
            if ($_ -match '^([^=]+)=(.*)$') {
                Set-Item -Path "Env:$($Matches[1])" -Value $Matches[2]
            }
        }

    $env:PYO3_CROSS = '1'
    $env:PYO3_CROSS_LIB_DIR = Join-Path $pythonSdk 'libs'
    $env:PYO3_CROSS_PYTHON_VERSION = $pythonMajorMinor
    $env:PYO3_CROSS_PYTHON_IMPLEMENTATION = 'CPython'
    $env:PYO3_USE_RAW_DYLIB = '0'
    $cargoArguments += @('--target', $rustTarget)
    $binaryPath = Join-Path $WORKER "target\$rustTarget\release\r2p2.exe"
} else {
    $env:PYO3_PYTHON = (Get-Command python).Source
}

Push-Location $WORKER
rustup run $rustToolchain cargo @cargoArguments
Pop-Location

# --- v2 + v1 runtimes + app SDK into the deps tree ------------------------
python -m pip install ./runtimes/v2 ./runtimes/v1 azure-functions `
    --no-compile --target $DEPS

# --- Stage the runtime worker-directory layout ----------------------------
Copy-Item $binaryPath "$DEPS\r2p2.exe" -Force
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
