param (
    [string]$pythonVersion
)

# Create venv
python -m venv .env
. .env\Scripts\Activate.ps1
python -m pip install "setuptools<68" wheel

# Install Bazel
choco install bazel --version=6.5.0 -y
refreshenv
bazel --version

Write-Host "=== Checking Python version being used ==="
.\.env\Scripts\python.exe --version
.\.env\Scripts\pip.exe --version

Write-Host "=== Cloning gRPC repo ==="
if (-not (Test-Path "grpc")) {
    git clone --recursive https://github.com/grpc/grpc
} else {
    cd grpc
    Write-Host "Repo already exists. Updating submodules..."
    git submodule update --init --recursive
    cd ..
}

cd grpc

Write-Host "=== Building grpcio wheel with setup.py ==="
..\.\.env\Scripts\python.exe setup.py bdist_wheel -d dist

Write-Host "=== Checking built wheels ==="
Get-ChildItem dist

Write-Host "=== Installing grpcio wheel into venv ==="
Get-ChildItem -Path "dist" -Filter "grpcio-*.whl" | ForEach-Object {
    Write-Host "Installing wheel: $($_.FullName)"
    ..\.\.env\Scripts\pip.exe install $_.FullName
}

cd ..

# Go back to your project root and install your workers package
Set-Location workers
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
