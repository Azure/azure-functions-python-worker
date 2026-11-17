# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# Offline regression tests: execute the build script with Python/Rust stubs.
$ErrorActionPreference = 'Stop'
$buildScript = Join-Path $PSScriptRoot '../scripts/r2p2_deps.ps1'
$root = Join-Path ([IO.Path]::GetTempPath()) "r2p2-windows-tests-$([guid]::NewGuid().ToString('N'))"
$savedLocation = Get-Location
$savedEnvironment = @{}
foreach ($name in @('BUILD_SOURCESDIRECTORY', 'PYO3_PYTHON', 'PYO3_CROSS',
                    'PYO3_CROSS_LIB_DIR', 'PYO3_CROSS_PYTHON_VERSION',
                    'PYO3_CROSS_PYTHON_IMPLEMENTATION', 'PYO3_USE_RAW_DYLIB')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name)
}
if (Get-Variable R2P2WindowsBuildTestState -Scope Global -ErrorAction SilentlyContinue) {
    throw 'R2P2 Windows test state already exists.'
}

function Assert-Equal($Actual, $Expected, [string]$Message) {
    if ($Actual -cne $Expected) { throw "$Message`: expected '$Expected', got '$Actual'." }
}
function Get-Command {
    param([string]$Name, $ErrorAction)
    if ($Name -eq 'python') {
        return [pscustomobject]@{ Source = $global:R2P2WindowsBuildTestState.PythonPath }
    }
    if ($Name -eq 'rustup') { return [pscustomobject]@{ Source = 'stub-rustup.exe' } }
    Microsoft.PowerShell.Core\Get-Command -Name $Name -ErrorAction Stop
}
function python {
    $global:LASTEXITCODE = 0
    $state = $global:R2P2WindowsBuildTestState
    if ($args[0] -eq '-c') {
        if ($args[1] -notlike '*struct.calcsize*') {
            throw "Unexpected Python query (ARM64 logic must not run): $args"
        }
        return $state.PointerWidth
    }
    if ($args[0] -ne '-m') { throw "Unexpected Python arguments: $args" }
    if ($args[1] -eq 'venv') {
        $scripts = Join-Path $env:BUILD_SOURCESDIRECTORY '.env/Scripts'
        New-Item -ItemType Directory -Path $scripts -Force | Out-Null
        [IO.File]::WriteAllText((Join-Path $scripts 'Activate.ps1'), '# no-op test venv')
    } elseif ($args[1] -eq 'pip') {
        # The fixture already contains the directories pip would create.
    } else { throw "Unexpected Python module: $args" }
}
function rustup {
    $global:LASTEXITCODE = 0
    $state = $global:R2P2WindowsBuildTestState
    $state.RustCalls.Add(($args -join ' '))
    if ($args.Count -ge 5 -and $args[2] -eq 'cargo' -and $args[3] -eq 'build') {
        $targetIndex = [Array]::IndexOf([object[]]$args, '--target')
        $target = if ($targetIndex -ge 0) { $args[$targetIndex + 1] } else { $null }
        Assert-Equal $target $state.Target 'Cargo target'
        Assert-Equal $env:PYO3_PYTHON $state.PythonPath 'Selected Python interpreter'
        foreach ($name in @('PYO3_CROSS', 'PYO3_CROSS_LIB_DIR', 'PYO3_CROSS_PYTHON_VERSION',
                            'PYO3_CROSS_PYTHON_IMPLEMENTATION', 'PYO3_USE_RAW_DYLIB')) {
            Assert-Equal ([string]::IsNullOrEmpty([Environment]::GetEnvironmentVariable($name))) $true "Unexpected $name"
        }
        $binary = if ($target) { "target/$target/release/r2p2.exe" } else { 'target/release/r2p2.exe' }
        $path = Join-Path (Get-Location) $binary
        New-Item -ItemType Directory -Path (Split-Path $path) -Force | Out-Null
        [IO.File]::WriteAllText($path, "built-$($state.Architecture)")
    }
}

try {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $null)
    }
    foreach ($architecture in @('x64', 'x86')) {
        $fixture = Join-Path $root $architecture
        foreach ($directory in @('workers/r2p2/bridge', 'workers/r2p2/target/release',
                                  'deps/azure_functions_runtime/utils', 'deps/azure_functions_runtime_v1/utils',
                                  'runtimes/v2/azure_functions_runtime/utils',
                                  'runtimes/v1/azure_functions_runtime_v1/utils')) {
            New-Item -ItemType Directory -Path (Join-Path $fixture $directory) -Force | Out-Null
        }
        foreach ($runtime in @('v2/azure_functions_runtime', 'v1/azure_functions_runtime_v1')) {
            foreach ($file in @('native_invocation.py', 'utils/executor.py')) {
                [IO.File]::WriteAllText((Join-Path $fixture "runtimes/$runtime/$file"), '# fixture')
            }
        }
        [IO.File]::WriteAllText((Join-Path $fixture 'workers/r2p2/bridge/fixture.txt'), 'bridge')
        [IO.File]::WriteAllText((Join-Path $fixture 'workers/.artifactignore'), '')
        # A stale native binary must never be packaged by the x86 target build.
        [IO.File]::WriteAllText((Join-Path $fixture 'workers/r2p2/target/release/r2p2.exe'), 'stale-native')
        $global:R2P2WindowsBuildTestState = @{
            Architecture = $architecture
            PointerWidth = if ($architecture -eq 'x86') { 32 } else { 64 }
            Target = if ($architecture -eq 'x86') { 'i686-pc-windows-msvc' } else { $null }
            PythonPath = Join-Path $fixture '.env/Scripts/python.exe'
            RustCalls = [Collections.Generic.List[string]]::new()
        }
        $env:BUILD_SOURCESDIRECTORY = $fixture
        & $buildScript -PythonVersion '3.15.2' -Architecture $architecture | Out-Null
        $state = $global:R2P2WindowsBuildTestState
        $expected = @('toolchain install stable-x86_64-pc-windows-msvc --profile minimal')
        if ($state.Target) { $expected += "target add $($state.Target) --toolchain stable-x86_64-pc-windows-msvc" }
        $expected += @('run stable-x86_64-pc-windows-msvc rustc --version',
                       'run stable-x86_64-pc-windows-msvc cargo --version')
        $build = 'run stable-x86_64-pc-windows-msvc cargo build --release --locked'
        if ($state.Target) { $build += " --target $($state.Target)" }
        $expected += $build
        Assert-Equal ($state.RustCalls -join '|') ($expected -join '|') "$architecture Rust commands"
        Assert-Equal ([IO.File]::ReadAllText((Join-Path $fixture 'deps/r2p2.exe'))) "built-$architecture" 'Staged binary'
        Assert-Equal ([IO.File]::ReadAllText((Join-Path $fixture 'deps/bridge/fixture.txt'))) 'bridge' 'Staged bridge'
    }

    # Wrong-bitness Python must still fail before Rust is installed or invoked.
    $global:R2P2WindowsBuildTestState.PointerWidth = 64
    $global:R2P2WindowsBuildTestState.RustCalls.Clear()
    $rejected = $false
    try { & $buildScript -PythonVersion '3.15.2' -Architecture x86 | Out-Null } catch {
        if ($_.Exception.Message -notlike '*must be 32-bit*') { throw }
        $rejected = $true
    }
    Assert-Equal $rejected $true 'Wrong-bitness rejection'
    Assert-Equal $global:R2P2WindowsBuildTestState.RustCalls.Count 0 'Rust calls after wrong-bitness rejection'

    # Exercise the actual shared build-plan statements for ARM64 without needing
    # a real SDK or VS installation. SDK-specific execution is tested separately.
    $tokens = $null; $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($buildScript, [ref]$tokens, [ref]$parseErrors)
    Assert-Equal $parseErrors.Count 0 'Build script parse errors'
    $statements = $ast.EndBlock.Statements
    $toolchainAssignment = $statements | Where-Object {
        $_ -is [Management.Automation.Language.AssignmentStatementAst] -and $_.Left.Extent.Text -eq '$rustToolchain'
    }
    $cargoAssignment = $statements | Where-Object {
        $_ -is [Management.Automation.Language.AssignmentStatementAst] -and $_.Left.Extent.Text -eq '$cargoArguments'
    }
    $sdkBlock = $statements | Where-Object {
        $_ -is [Management.Automation.Language.IfStatementAst] -and $_.Extent.Text.Contains('$env:PYO3_CROSS =')
    }
    Assert-Equal @($sdkBlock).Count 1 'SDK configuration block count'
    Assert-Equal $sdkBlock.Clauses[0].Item1.Extent.Text '$Architecture -eq ''arm64''' 'SDK-only condition'
    $source = [IO.File]::ReadAllText($buildScript)
    $plan = $source.Substring($toolchainAssignment.Extent.StartOffset,
                             $cargoAssignment.Extent.StartOffset - $toolchainAssignment.Extent.StartOffset) +
            $source.Substring($cargoAssignment.Extent.StartOffset,
                             $sdkBlock.Extent.StartOffset - $cargoAssignment.Extent.StartOffset)
    $Architecture = 'arm64'
    $WORKER = Join-Path $root 'arm64/workers/r2p2'
    $global:R2P2WindowsBuildTestState.RustCalls.Clear()
    . ([scriptblock]::Create($plan))
    Assert-Equal $rustToolchain 'stable-x86_64-pc-windows-msvc' 'ARM64 host toolchain'
    Assert-Equal $rustTarget 'aarch64-pc-windows-msvc' 'ARM64 target'
    Assert-Equal ($cargoArguments -join ' ') 'build --release --locked --target aarch64-pc-windows-msvc' 'ARM64 Cargo arguments'
    Assert-Equal $binaryPath (Join-Path $WORKER 'target/aarch64-pc-windows-msvc/release/r2p2.exe') 'ARM64 artifact path'
    if (-not $global:R2P2WindowsBuildTestState.RustCalls.Contains(
        'target add aarch64-pc-windows-msvc --toolchain stable-x86_64-pc-windows-msvc')) {
        throw 'ARM64 target standard library was not installed.'
    }
    Write-Host 'All R2P2 Windows build regression tests passed (x64, x86, ARM64 plan, wrong-bitness guard).'
} finally {
    Set-Location $savedLocation
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name])
    }
    Remove-Variable R2P2WindowsBuildTestState -Scope Global -ErrorAction SilentlyContinue
    if (Test-Path $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}