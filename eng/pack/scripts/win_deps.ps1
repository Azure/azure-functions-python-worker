param (
    [string]$pythonVersion
)
$versionParts = $pythonVersion -split '\.'  # Splitting by dot
$versionMinor = [int]$versionParts[1]

python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install "setuptools>=62,<82.0"

cd workers
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
    # Vendored google.protobuf is built into the source tree by vendor_deps
    # (invoked from build-protos). Merge it into deps/ so CopyFiles@2 picks it up.
    $vendoredPath = Join-Path -Path $depsPath -ChildPath "azure_functions_worker/_vendored"
    New-Item -ItemType Directory -Force -Path $vendoredPath | Out-Null
    Copy-Item -Path "azure_functions_worker/_vendored/*" -Destination $vendoredPath.ToString() -Recurse -Force
} else {
    $protosPath = Join-Path -Path $depsPath -ChildPath "proxy_worker/protos"
    Copy-Item -Path "proxy_worker/protos/*" -Destination $protosPath.ToString() -Recurse -Force
}
