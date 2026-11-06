# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
param(
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$Sha256,
    [Parameter(Mandatory = $true)][string]$PythonVersion,
    [Parameter(Mandatory = $true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if ($PythonVersion -notmatch '^(\d+)\.(\d+)\.\d+(?:(?:a|b|rc)\d+)?$') {
    throw 'Windows ARM64 SDK requires an exact CPython release version.'
}
$libraryStem = "python$($Matches[1])$($Matches[2])"
if ($Sha256 -notmatch '\A[0-9a-fA-F]{64}\z') {
    throw 'CPYTHON_ARM64_SHA256 must contain exactly 64 hexadecimal characters.'
}
if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
    throw "The pipeline-staged CPython archive does not exist: $Archive"
}
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash -ne $Sha256) {
    throw 'CPython Windows ARM64 SDK SHA-256 mismatch.'
}
if (Test-Path -LiteralPath $Destination) {
    throw "SDK destination must not already exist: $Destination"
}
# NuGet packages are ZIP archives; preserve their original signed bytes at intake.
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($Archive, $Destination)
$sdk = Join-Path $Destination 'tools'
foreach ($required in @('include/Python.h', 'include/patchlevel.h', "libs/$libraryStem.lib", "$libraryStem.dll")) {
    if (-not (Test-Path -LiteralPath (Join-Path $sdk $required) -PathType Leaf)) {
        throw "The ARM64 CPython SDK is missing $required."
    }
}
$header = Get-Content -LiteralPath (Join-Path $sdk 'include/patchlevel.h') -Raw
$version = [regex]::Match($header, '(?m)^#define PY_VERSION\s+"([^"\r\n]+)"\r?$')
if (-not $version.Success -or $version.Groups[1].Value -ne $PythonVersion) {
    throw "Expected CPython $PythonVersion SDK; archive contains a different or unknown version."
}
$dll = [System.IO.File]::ReadAllBytes((Join-Path $sdk "$libraryStem.dll"))
if ($dll.Length -lt 64 -or $dll[0] -ne 0x4d -or $dll[1] -ne 0x5a) {
    throw 'Invalid CPython DLL DOS header.'
}
$pe = [BitConverter]::ToInt32($dll, 0x3c)
if ($pe -lt 0 -or $pe + 6 -gt $dll.Length -or
    [BitConverter]::ToUInt32($dll, $pe) -ne 0x00004550 -or
    [BitConverter]::ToUInt16($dll, $pe + 4) -ne 0xaa64) {
    throw 'CPython DLL must be an ARM64 PE image.'
}
# Check every COFF/import object, not just the DLL: an x64 .lib cannot link ARM64.
$lib = [System.IO.File]::ReadAllBytes((Join-Path $sdk "libs/$libraryStem.lib"))
if ($lib.Length -lt 8 -or [Text.Encoding]::ASCII.GetString($lib, 0, 8) -ne "!<arch>`n") {
    throw 'Invalid CPython import-library archive.'
}
$offset = 8
$objects = 0
while ($offset -lt $lib.Length) {
    if ($offset + 60 -gt $lib.Length -or
        [Text.Encoding]::ASCII.GetString($lib, $offset + 58, 2) -ne ([string][char]0x60 + "`n")) {
        throw 'Invalid import-library member header.'
    }
    $name = [Text.Encoding]::ASCII.GetString($lib, $offset, 16).Trim()
    $size = 0
    if (-not [int]::TryParse([Text.Encoding]::ASCII.GetString($lib, $offset + 48, 10).Trim(), [ref]$size) -or
        $size -lt 0 -or $size -gt $lib.Length - $offset - 60) {
        throw 'Invalid import-library member size.'
    }
    $start = $offset + 60
    if ($name -notin @('/', '//', '/SYM64/')) {
        if ($size -lt 20) { throw 'Invalid COFF import-library object.' }
        $machineOffset = if ([BitConverter]::ToUInt16($lib, $start) -eq 0 -and
            [BitConverter]::ToUInt16($lib, $start + 2) -eq 0xffff) { 6 } else { 0 }
        if ([BitConverter]::ToUInt16($lib, $start + $machineOffset) -ne 0xaa64) {
            throw 'CPython import library must contain only ARM64 objects.'
        }
        $objects++
    }
    $offset = $start + $size + ($size % 2)
}
if ($objects -eq 0) { throw 'CPython import library contains no ARM64 objects.' }
Write-Host "Verified CPython $PythonVersion Windows ARM64 SDK SHA-256: $Sha256"
return $sdk