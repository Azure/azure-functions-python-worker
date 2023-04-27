python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip

python -m pip install . --use-pep517

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

python -m pip install . azure-functions --use-pep517 --no-compile --target $depsPath.ToString()
