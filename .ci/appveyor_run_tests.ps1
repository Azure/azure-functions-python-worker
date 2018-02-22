$env:PYAZURE_WEBHOST_DLL = "$(Get-Location)\$($env:PYAZURE_WEBHOST_PATH)\$($env:PYAZURE_WEBHOST_EXECUTABLE)"
& $env:PYTHON setup.py test
