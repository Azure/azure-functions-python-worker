param (
    [string]$pythonVersion
)
$versionParts = $pythonVersion -split '\.'  # Splitting by dot
$versionMinor = [int]$versionParts[1]

Write-Host "=== Upgrading pip and installing build dependencies ==="
python -m pip install --upgrade pip setuptools wheel cython

Write-Host "=== Cloning gRPC repo ==="
if (Test-Path grpc) {
    Remove-Item -Recurse -Force grpc
}
git clone --recursive https://github.com/grpc/grpc

Write-Host "=== Building grpcio from source ==="
Set-Location grpc
$env:GRPC_PYTHON_BUILD_WITH_CYTHON = "1"

# Build the wheel into dist/
python -m pip wheel . -w dist

# Log contents of dist
Write-Host "=== Checking dist directory ==="
if (Test-Path dist) {
    Get-ChildItem dist
} else {
    Write-Host "dist/ directory not found!"
}

# Log and install grpc
$grpcWheel = Get-ChildItem dist\grpcio-*.whl | Select-Object -First 1
Write-Host "Built grpcio wheel: $($grpcWheel.Name)"
Write-Host "=== Install grpcio wheel $($grpcWheel.Name) into root ==="
$grpcWheel = Get-ChildItem dist\grpcio-*.whl | Select-Object -First 1
python -m pip install $grpcWheel.FullName

cd ..

# Change back to project root
Set-Location workers

Write-Host "=== Install other deps into root ==="
python -m pip install .
python -m pip install grpcio-tools==1.70.0

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

# Install both grpc wheels into deps
Write-Host "=== Installing grpcio into deps/ ==="
python -m pip install $grpcWheel.FullName --target $depsPath

Write-Host "=== Installing other deps into deps/ ==="
python -m pip install --upgrade pip setuptools wheel cython --target $depsPath 
python -m pip install . azure-functions --no-compile --target $depsPath --find-links ..\grpc\dist
python -m pip install grpcio-tools==1.70.0 --no-compile --target $depsPath --find-links ..\grpc\dist

Write-Host "=== Install invoke and build protos ==="
python -m pip install invoke
cd tests
python -m invoke -c test_setup build-protos

Write-Host "=== Copying .artifactignore ==="
cd ..
Copy-Item -Path ".artifactignore" -Destination $depsPath.ToString()

Write-Host "=== Copying protos ==="
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