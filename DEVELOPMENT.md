# Setting up development environment

1. Clone the repository:

```shell
$ git clone --recursive https://github.com/Azure/azure-functions-python-worker.git
$ git checkout dev
```

2. Create a virtual environment:

```shell
$ python3.6 -m venv worker_env
```

3. Activate the virtual environment:

```shell
$ source worker_env/bin/activate
```

4. Change the directory to the root of the cloned repository:

```shell
$ cd azure-functions-python-worker
```

5. Create a `.testconfig` file with the following contents (don't forget
   to change `/MY/LOCAL/PATH/TO` to a real path on your machine):

```
[webhost]
dll = /MY/LOCAL/PATH/TO/SiteExtensions/Functions/Microsoft.Azure.WebJobs.Script.WebHost.dll
```

6. Setup the 'azure' package in your new virtual environment
   in development mode:

```shell
$ pip install -U -e .[dev]
```


# Running tests

1. Activate the dev virtual environment:

```shell
$ source worker_env/bin/activate
```

2. Change the directory to the root of the cloned repository:

```shell
$ cd azure-functions-python-worker
```

3. Run tests with pytest:

```shell
$ pytest
```


# Running a web host to call test functions

1. Activate the dev virtual environment:

```shell
$ source worker_env/bin/activate
```

2. Change the directory to the root of the cloned repository:

```shell
$ cd azure-functions-python-worker
```

3. Start a local webhost:

```shell
$ python -m azure.worker.testutils
```
