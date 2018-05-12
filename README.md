[![Build Status](https://travis-ci.org/Azure/azure-functions-python-worker.svg?branch=dev)](https://travis-ci.org/Azure/azure-functions-python-worker)
[![Build status](https://ci.appveyor.com/api/projects/status/github/azure/azure-functions-python-worker?svg=true&branch=dev)](https://ci.appveyor.com/project/appsvc/azure-functions-python-worker)

This repository will host the Python language worker impelementation for Azure Functions. We'll also be using it to track work items related to Python support. Feel free to leave comments about any of the features/design patterns.

## Disclaimer
The project is currently in progress. Please **do not use in production** as we expect the feature and design patterns to develop and change over time.

## Overview
Python support for Functions is based on Python 3.6 and the Functions v2 runtime. Since the v2 runtime is cross-platform, you can develop and test on any platform (Windows, MacOS or Linux). 

On Azure, there are two ways to publish a Python function: 

1. Bring your files (Linux)

   **Get Started:** 
   - [Functions Core Tools (CLI)](https://github.com/Azure/azure-functions-python-worker/wiki/Create-Function-(CLI))
   - VS Code [TBD]
   
   **Known issues:**
   
   TBD

2. Bring your custom image (Docker)

## Reference

| Item | Link |
|-----------------------|--------------------|
|Python Developer Guide | [link](https://pythondeveloperguide.azurewebsites.net/) |
|Binding API Reference | [link](https://pythondeveloperguide.azurewebsites.net/api.html#azure-functions-reference) |


## Contributing

| Item | Link |
|-----------------------|--------------------|
|Language worker architecture | [link](https://github.com/Azure/azure-functions-python-worker/wiki/Worker-Architecture) |
|Contriutor setup | [link]() |
|Adding support for a binding | [link]() |

This project welcomes contributions and suggestions.  Most contributions require you to agree to a
Contributor License Agreement (CLA) declaring that you have the right to, and actually do, grant us
the rights to use your contribution. For details, visit https://cla.microsoft.com.

When you submit a pull request, a CLA-bot will automatically determine whether you need to provide
a CLA and decorate the PR appropriately (e.g., label, comment). Simply follow the instructions
provided by the bot. You will only need to do this once across all repos using our CLA.

This project has adopted the [Microsoft Open Source Code of Conduct](https://opensource.microsoft.com/codeofconduct/).
For more information see the [Code of Conduct FAQ](https://opensource.microsoft.com/codeofconduct/faq/) or
contact [opencode@microsoft.com](mailto:opencode@microsoft.com) with any additional questions or comments.
