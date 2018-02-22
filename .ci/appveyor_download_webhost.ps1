if (!(Test-Path $Env:PYAZURE_WEBHOST_PATH\$Env:PYAZURE_WEBHOST_EXECUTABLE)) {
    if (!(Test-Path $Env:PYAZURE_WEBHOST_PATH)) {
        New-Item $Env:PYAZURE_WEBHOST_PATH -ItemType Directory
    }

    $url = "http://ci.appveyor.com/api/buildjobs/y6wonxc4o3k529s8/artifacts/Functions.Binaries.2.0.11549-alpha.zip"
    $zipfile = "$([System.IO.Path]::GetTempFileName()).zip"
    (New-Object System.Net.WebClient).DownloadFile($url, $zipfile)

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory(
        $zipfile, $Env:PYAZURE_WEBHOST_PATH)

    Expand-Archive -Path $zipfile -DestinationPath $Env:PYAZURE_WEBHOST_PATH
    Remove-Item $zipfile
}
