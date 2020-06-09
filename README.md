<img src="./docs/Azure.Functions.svg" width = "180" alt="Functions Header Image">

|Branch|Status|Coverage|
|---|---|---|
|master|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions%20Python/_apis/build/status/Azure%20Functions%20Python-CI?branchName=master)](https://azfunc.visualstudio.com/Azure%20Functions%20Python/_build/latest?definitionId=3&branchName=master)|![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/azfunc/Azure%20Functions%20Python/3/master)
|dev|[![Build Status](https://azfunc.visualstudio.com/Azure%20Functions%20Python/_apis/build/status/Azure%20Functions%20Python-CI?branchName=dev)](https://azfunc.visualstudio.com/Azure%20Functions%20Python/_build/latest?definitionId=3&branchName=dev)|![Azure DevOps coverage](https://img.shields.io/azure-devops/coverage/azfunc/Azure%20Functions%20Python/3/dev)

# Overview

Python support for Azure Functions is based on Python 3.6, Python 3.7, and Python 3.8, serverless hosting on Linux and the Functions 2.0 and 3.0 runtime.

Here is the current status of Python in Azure Functions:

What are the supported Python versions?

|Azure Functions Runtime|Python 3.6|Python 3.7|Python 3.8|
|-----------------------|----------|----------|----------|
|Azure Functions 2.0|✔|✔| |
|Azure Functions 3.0|✔|✔|✔|

What's available?

- Build, test, debug and publish using Azure Functions Core Tools (CLI) or Visual Studio Code
- Deploy Python Function project onto consumption, dedicated, or elastic premium plan.
- Deploy Python Function project in a custom docker image onto dedicated, or elastic premium plan.
- Triggers / Bindings : HTTP, Blob, Queue, Timer, Cosmos DB, Event Grid, Event Hubs and Service Bus
- Triggers / Bindings : Custom binding support

What's coming?

- [Durable Functions For Python](https://github.com/Azure/azure-functions-durable-python)

# Get Started

- [Create your first Python function](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-first-function-python)
- [Developer guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Binding API reference](https://docs.microsoft.com/en-us/python/api/azure-functions/azure.functions?view=azure-python)
- [Develop using VS Code](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-first-function-vs-code)
- [Create a Python Function on Linux using a custom docker image](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-function-linux-custom-image)

# Give Feedback

Issues and feature requests are tracked in a variety of places. To report this feedback, please file an issue to the relevant repository below:

|Item|Description|Link|
|----|-----|-----|
| Python Worker | Programming Model, Triggers & Bindings |[File an Issue](https://github.com/Azure/azure-functions-python-worker/issues)|
| Linux | Base Docker Images |[File an Issue](https://github.com/Azure/azure-functions-docker/issues)|
| Runtime | Script Host & Language Extensibility |[File an Issue](https://github.com/Azure/azure-functions-host/issues)|
| VSCode | VSCode Extension for Azure Functions |[File an Issue](https://github.com/microsoft/vscode-azurefunctions/issues)
| Core Tools | Command Line Interface for Local Development |[File an Issue](https://github.com/Azure/azure-functions-core-tools/issues)|
| Portal | User Interface or Experience Issue |[File an Issue](https://github.com/azure/azure-functions-ux/issues)|
| Templates | Code Issues with Creation Template |[File an Issue](https://github.com/Azure/azure-functions-templates/issues)|

# Contribute

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

Here are some pointers to get started:

- [Language worker architecture](https://github.com/Azure/azure-functions-python-worker/wiki/Worker-Architecture)
- [Setting up the development environment](https://github.com/Azure/azure-functions-python-worker/wiki/Contributor-Guide)
- [Adding support for a new binding](https://github.com/Azure/azure-functions-python-worker/wiki/Adding-support-for-a-new-binding-type)
- [Release instructions](https://github.com/Azure/azure-functions-python-worker/wiki/Release-Instructions)

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
