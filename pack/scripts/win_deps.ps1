python -m venv .env
.env\Scripts\Activate.ps1
python -m pip install --upgrade pip==23.0

python -m pip install .

$depsPath = Join-Path -Path $env:BUILD_SOURCESDIRECTORY -ChildPath "deps"

python -m pip install . azure-functions --no-compile --target $depsPath.ToString()
