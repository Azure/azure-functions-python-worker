# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
$ErrorActionPreference = 'Stop'
$verifier = Join-Path $PSScriptRoot '../scripts/verify_cpython_windows_sdk.ps1'
$root = Join-Path ([IO.Path]::GetTempPath()) "cpython-sdk-tests-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $root | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
function New-Fixture([string]$Name, [string]$Version = '3.15.2', [uint16]$DllMachine = 0xaa64,
                     [uint16]$LibMachine = 0xaa64, [switch]$MissingHeader, [switch]$InvalidLibrary) {
    $tree = Join-Path $root $Name
    New-Item -ItemType Directory -Path "$tree/tools/include", "$tree/tools/libs" | Out-Null
    if (-not $MissingHeader) { [IO.File]::WriteAllText("$tree/tools/include/Python.h", '/* fixture */') }
    [IO.File]::WriteAllText("$tree/tools/include/patchlevel.h", "#define PY_VERSION              `"$Version`"`n")
    $dll = New-Object byte[] 128
    $dll[0] = 0x4d; $dll[1] = 0x5a
    [BitConverter]::GetBytes([int]64).CopyTo($dll, 0x3c)
    [BitConverter]::GetBytes([uint32]0x00004550).CopyTo($dll, 64)
    [BitConverter]::GetBytes($DllMachine).CopyTo($dll, 68)
    [IO.File]::WriteAllBytes("$tree/tools/python315.dll", $dll)
    $object = New-Object byte[] 20
    # Short COFF import object: signature 0, 0xffff; machine at offset 6.
    $object[2] = 0xff; $object[3] = 0xff
    [BitConverter]::GetBytes($LibMachine).CopyTo($object, 6)
    $member = 'python315.dll/'.PadRight(16) + '0'.PadRight(12) + '0'.PadRight(6) +
        '0'.PadRight(6) + '0'.PadRight(8) + '20'.PadRight(10) + [char]0x60 + "`n"
    $lib = [Text.Encoding]::ASCII.GetBytes("!<arch>`n" + $member) + $object
    if ($InvalidLibrary) { $lib = [byte[]]@(1, 2, 3) }
    [IO.File]::WriteAllBytes("$tree/tools/libs/python315.lib", $lib)
    $archive = "$tree.nupkg"
    [IO.Compression.ZipFile]::CreateFromDirectory($tree, $archive)
    return $archive
}
function Invoke-Check([string]$Archive, [string]$Digest, [string]$Version = '3.15.2') {
    & $verifier -Archive $Archive -Sha256 $Digest -PythonVersion $Version `
        -Destination (Join-Path $root "extracted-$([guid]::NewGuid().ToString('N'))")
}
function Assert-Rejected([scriptblock]$Action, [string]$Message) {
    $rejected = $false
    try { & $Action | Out-Null } catch {
        if ($_.Exception.Message -notlike "*$Message*") { throw }
        $rejected = $true
    }
    if (-not $rejected) { throw "Expected rejection: $Message" }
}
try {
    $archive = New-Fixture 'valid'
    $digest = (Get-FileHash $archive -Algorithm SHA256).Hash
    $sdk = Invoke-Check $archive $digest
    if (-not (Test-Path "$sdk/include/Python.h")) { throw 'SDK tools directory was not returned.' }
    Invoke-Check $archive $digest.ToLowerInvariant() | Out-Null
    Assert-Rejected { Invoke-Check $archive ('0' * 64) } 'SHA-256 mismatch'
    Assert-Rejected { Invoke-Check $archive 'bad' } '64 hexadecimal'
    Assert-Rejected { Invoke-Check $archive ($digest + "`n") } '64 hexadecimal'
    Assert-Rejected { Invoke-Check "$root/missing.nupkg" $digest } 'does not exist'
    Assert-Rejected { Invoke-Check $archive $digest '3.15' } 'exact CPython'
    foreach ($case in @(
        @{ Name = 'wrong-version'; Version = '3.15.1'; Expected = 'Expected CPython' }
        @{ Name = 'x64-dll'; DllMachine = [uint16]0x8664; Expected = 'ARM64 PE' }
        @{ Name = 'x64-lib'; LibMachine = [uint16]0x8664; Expected = 'only ARM64 objects' }
        @{ Name = 'missing-header'; MissingHeader = $true; Expected = 'missing include/Python.h' }
        @{ Name = 'invalid-lib'; InvalidLibrary = $true; Expected = 'Invalid CPython import-library' }
    )) {
        $expected = $case.Expected
        $arguments = $case.Clone(); $arguments.Remove('Expected')
        $fixture = New-Fixture @arguments
        $hash = (Get-FileHash $fixture -Algorithm SHA256).Hash
        Assert-Rejected { Invoke-Check $fixture $hash } $expected
    }
    # Exercise the actual build entry point: tampered bytes fail before Python setup.
    $savedRoot = $env:BUILD_SOURCESDIRECTORY
    $savedTemp = $env:AGENT_TEMPDIRECTORY
    $savedArchive = $env:CPYTHON_ARM64_ARCHIVE
    $savedDigest = $env:CPYTHON_ARM64_SHA256
    $savedLocation = Get-Location
    try {
        $env:BUILD_SOURCESDIRECTORY = $root
        $env:AGENT_TEMPDIRECTORY = $root
        $env:CPYTHON_ARM64_ARCHIVE = $archive
        $env:CPYTHON_ARM64_SHA256 = '0' * 64
        Assert-Rejected { & "$PSScriptRoot/../scripts/r2p2_deps.ps1" -PythonVersion '3.15.2' -Architecture arm64 } 'SHA-256 mismatch'
        if (Test-Path "$root/.env") { throw 'Python setup ran before SDK verification.' }
    } finally {
        $env:BUILD_SOURCESDIRECTORY = $savedRoot
        $env:AGENT_TEMPDIRECTORY = $savedTemp
        $env:CPYTHON_ARM64_ARCHIVE = $savedArchive
        $env:CPYTHON_ARM64_SHA256 = $savedDigest
        Set-Location $savedLocation
    }
    Write-Host 'All CPython Windows ARM64 SDK verification tests passed.'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force
}