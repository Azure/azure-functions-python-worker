[![Build Status](https://travis-ci.org/Azure/azure-functions-python-worker.svg?branch=dev)](https://travis-ci.org/Azure/azure-functions-python-worker)
[![Build status](https://ci.appveyor.com/api/projects/status/github/azure/azure-functions-python-worker?svg=true&branch=dev)](https://ci.appveyor.com/project/appsvc/azure-functions-python-worker)

This repository will host the Python language worker impelementation for Azure Functions. We'll also be using it to track work items related to Python support. Please feel free to leave comments about any of the features and design patterns.

> :construction: The project is currently **work in progress**. Please **do not use in production** as we expect developments over time. :construction:

# Overview

Python support for Functions is based on [Python3.6](https://www.python.org/downloads/release/python-360/), [Functions on Linux](https://blogs.msdn.microsoft.com/appserviceteam/2017/11/15/functions-on-linux-preview/) and the [V2 Runtime](https://docs.microsoft.com/en-us/azure/azure-functions/functions-versions).

Here is the current status of Python on Functions:

| Area | Feature | Status |
|------|---------|--------|
| Language Worker | [Triggers and Bindings](https://docs.microsoft.com/en-us/azure/azure-functions/functions-triggers-bindings) | In progress |
| Tools | [Functions Core Tools (CLI)](https://docs.microsoft.com/en-us/azure/azure-functions/functions-run-local)| Available |
| Tools | [Visual Studio Code](https://code.visualstudio.com/tutorials/functions-extension/getting-started) | In progress |
| Tools | [Azure Portal Editing](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-first-azure-function) | In progress |
| Hosting | Linux - [app service plan](https://docs.microsoft.com/en-us/azure/azure-functions/functions-scale#app-service-plan) | Available |
| Hosting | Linux - [consumption plan](https://docs.microsoft.com/en-us/azure/azure-functions/functions-scale#consumption-plan) | In progress |
| Hosting | [Bring your own custom image](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-function-linux-custom-image) | Available |

# Get Started

- [Build and publish using the Functions Core Tools](https://github.com/Azure/azure-functions-python-worker/wiki/Create-Function-(CLI))
- [Python developer guide](https://pythondeveloperguide.azurewebsites.net/)
- [Binding API reference](https://pythondeveloperguide.azurewebsites.net/api.html#azure-functions-reference)

# Give Feedback

Issues and feature requests are tracked in a variety of places. To report this feedback, please file an issue to the relevant respository below:

|Item|Description|Link|
|----|-----|-----|
|Runtime|Script Host, Triggers & Bindings, Language Support|[File an Issue](https://github.com/Azure/azure-functions-host/issues)|
|Core Tools|Command line interface for local development|[File an Issue](https://github.com/Azure/azure-functions-core-tools/issues)|
|Portal|User Interface or Experience Issue|[File an Issue](https://github.com/azure/azure-functions-ux/issues)|
|Templates|Code Issues with Creation Template|[File an Issue](https://github.com/Azure/azure-functions-templates/issues)|

# Contribute

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

Here are some pointers to get started:

- [Language worker architecture](https://github.com/Azure/azure-functions-python-worker/wiki/Worker-Architecture)
- [Setting up the development environment](https://github.com/Azure/azure-functions-python-worker/wiki/Contributor-Guide)
- [Adding support for a new binding](https://github.com/Azure/azure-functions-python-worker/wiki/Adding-support-for-a-new-binding-type)

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
