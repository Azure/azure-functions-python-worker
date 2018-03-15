[![Build Status](https://travis-ci.org/Azure/azure-functions-python-worker.svg?branch=dev)](https://travis-ci.org/Azure/azure-functions-python-worker)
[![Build status](https://ci.appveyor.com/api/projects/status/github/azure/azure-functions-python-worker?svg=true&branch=dev)](https://ci.appveyor.com/project/appsvc/azure-functions-python-worker)

This repository will host the Python language worker impelementation for Azure Functions. We'll also be using it to track work items related to first class Python support. Feel free to leave comments about any of the features/design patterns.

# Prerequisites
- [Python 3.6.4](https://www.python.org/downloads/release/python-364/)
- [Azure Functions Core Tools](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local#install-the-azure-functions-core-tools)
- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/?view=azure-cli-latest)

# Programming Model

Script file : `main.py`

Entry point : `main()`

Below is a sample structure of a Python function app - 
```
MyPythonApp
    |__host.json
    |__HttpTriggerFunction
        |__main.py
        |__function.json
    |__TimerTriggerFunction
        |__main.py
        |__function.json
    |__requirements.txt
```

## Function Format

The `main()` method serves as the primary entry for your Python script. 

Since only a single Python process can exist per function app, it is resocmmended to implement `main()` as an asynchronous coroutine using the `async def` statement. 

```python
# Would be run with asyncio directly
async def main():
    await some_nonblocking_socket_io_op()
```
If the `main()` function is synchronous (no `async` qualifier) we automatically run it in an asyncio thread-pool.
```python
# Would be run in an asyncio thread-pool
def main():
    some_blocking_socket_io()
```

## Triggers and Bindings

Trigger data and bindings can be communicated to the function via method arguments whose names are specified in `function.json`.

### Input Bindings
A function can have two types of inputs: **1. trigger input** and **2. additional input**. Their usage is identical in the Python code. See example below - 

```python
# main.py
def main(trigger_input, binding_input):
	# functions logic here
```

### Output Bindings

Outputs can be expressed in two ways - **1. return value** and **2. output parameters**. If there's only one output, we recommend using it as the return value. For multiple outputs, you'll have to use the method arguments.

To use the return value of your function as an output binding, label it using `"name" : "$return"` in `function.json`. See example below - 

```javascript
//function.json
{ 
	"direction": "in", 
	"name": "my_input"
},
{ 
	"direction": "out", 
	"name": "$return"
}
```
```python
# main.py
def main(my_input):
    # function logic here
    return 'Value of the output binding.'
```

To produce multiple outputs, use the named function arguments of type ```azure.functions.Out``` . For example - 

```javascript
// function.json
{
    "name": "trigger_input",
    "direction": "in"
},
{
    "name": "$return",
    "direction": "out"
},
{
    "name": "other_output",
    "direction": "out",
}
```

```python
# main.py
import azure.functions

def main(trigger_input, other_output: azure.functions.Out):
    other_output.set(trigger_input)
    return 'Value of the output binding.'
```

## Data Types
You can use function annotations (type hints) to define the data type of binding arguments. The runtime will use this information to validate the type before passing data into and returning data from a function execution. For example - 

```python
# main.py
def main(my_input : str) -> bool:
	# function logic here
	return True

```

## HTTP Triggers and Bindings
HTTP webhook triggers and HTTP output bindings will use **request** and **response** objects to represent the HTTP messaging. 

#### Request Object
The **request** object has the following attributes.

**Attribute** | **Data Type** | **Description**
-------------|----------|----------------
method | str | HTTP method of the request
url | str | Url of the request
headers | dict | HTTP headers sent with the request
params | dict | Query string parameters
body | bytes | Raw HTTP request body

#### Response Object
The **response** object has the following attributes.

**Attribute** | **Data Type** | **Description**
-------------|----------|----------------
headers | dict | Response headers
status_code | int | HTTP response status code
body | str, bytes, dict | Contents of the response

Similar to any other binding, these can be accessed using the `name` attribute in `function.json`.

## Logging
In order to write traces during an execution, we'll use Python's **logging** module. 

```python
# main.py
import logging

logger = logging.getLogger('my function')

def main(req):
    logger.info('Starting execution of Python function')
    # function logic here
```

The module provides various convenience methods that let you write to the console at more than one trace level. 

Method | Description
--------|------------
**debug**(message)|Detailed information, typically of interest only when diagnosing problems.
**info**(message)| Confirmation that things are working as expected.
**warning**(message)| An indication that something unexpected happened, or indicative of some problem in the near future (e.g. ‘disk space low’). The software is still working as expected.
**error**(message)| Due to a more serious problem, the software has not been able to perform some function.
**critical**(message)| A serious error, indicating that the program itself may be unable to continue running.

By default, the effective level for logger will be set to INFO. To modify this level, use the `setLevel()` method provided by the logging module. 

**Note:** Since we use a single Python process per function app, using the inbuilt **print** utility will output to our system logs. These are not available to the user and hard to distinguish on a per function basis.


# Disclaimer
The project is currently in progress. Please expect the feature and design patterns to develop or change over time. If you have any feedback or requests, you can file an issue or add comments.

# Contributing

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
