Write-Host "Downloading Functions Core Tools...."
Invoke-RestMethod -Uri 'https://functionsclibuilds.blob.core.windows.net/builds/2/latest/version.txt' -OutFile version.txt
Write-Host "Using Functions Core Tools version: $(Get-Content -Raw version.txt)"
Remove-Item version.txt

$currDir = Get-Location
$output = "$currDir\Azure.Functions.Cli"


if (-not (Test-Path env:CORE_TOOLS_URL)) 
{ 
    $env:CORE_TOOLS_URL = "https://functionsclibuilds.blob.core.windows.net/builds/2/latest/Azure.Functions.Cli.win-x86.zip"
}

if (Test-Path env:CORE_TOOLS_EXE_PATH)
{
    $output = Split-Path $env:CORE_TOOLS_EXE_PATH
}

Write-Host "CORE_TOOLS_URL: $env:CORE_TOOLS_URL"
$wc = New-Object System.Net.WebClient
$wc.DownloadFile($env:CORE_TOOLS_URL, "$output.zip")

Write-Host "Extracting Functions Core Tools...."
Expand-Archive "$output.zip" -DestinationPath "$output"