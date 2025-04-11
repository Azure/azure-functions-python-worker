param (
    [string]$pythonVersion
)
$versionParts = $pythonVersion -split '\.'  # Splitting by dot
$versionMinor = [int]$versionParts[1]

python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip

python -m pip install .

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

python -m pip install . azure-functions --no-compile --target $depsPath.ToString()

python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

cd ..
Copy-Item -Path ".artifactignore" -Destination $depsPath.ToString()

if ($versionMinor -lt 13) {
    $protosPath = Join-Path -Path $depsPath -ChildPath "azure_functions_worker/protos"
    Copy-Item -Path "azure_functions_worker/protos/*" -Destination $protosPath.ToString() -Recurse -Force
} else {
    $protosPath = Join-Path -Path $depsPath -ChildPath "proxy_worker/protos"
    Copy-Item -Path "proxy_worker/protos/*" -Destination $protosPath.ToString() -Recurse -Force
}
