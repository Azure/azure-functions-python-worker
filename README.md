# <img src="https://raw.githubusercontent.com/Azure/azure-functions-python-worker/dev/docs/Azure.Functions.svg" width = "30" alt="Functions Header Image - Lightning Logo"> Azure Functions Python Worker

| Branch | Build Status                                                                                                                                                             | CodeCov                                                                                                                                                        | Test Status                                                                                                                                                             |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| dev    | [![Build Status](https://img.shields.io/azure-devops/build/azfunc/public/658/dev)](https://azfunc.visualstudio.com/public/_build/latest?definitionId=658&branchName=dev) | [![codecov](https://codecov.io/gh/Azure/azure-functions-python-worker/branch/dev/graph/badge.svg)](https://codecov.io/gh/Azure/azure-functions-python-worker)  | [![Test Status](https://img.shields.io/azure-devops/build/azfunc/public/658/dev)](https://azfunc.visualstudio.com/public/_build/latest?definitionId=658&branchName=dev) |

Python support for Azure Functions is based on Python 3.11, 3.12, 3.13, 3.14, and 3.15 serverless hosting on Linux and the Functions 4.0 runtime.

Here is the current status of Python in Azure Functions:

What are the supported Python versions?

| Azure Functions Runtime          | Python 3.11 | Python 3.12 | Python 3.13 | Python 3.14 | Python 3.15 |
|----------------------------------|-------------|-------------|-------------|-------------|-------------|
| Azure Functions 4.0              | ✔           | ✔           | ✔           | ✔           | ✔           |

For information about Azure Functions Runtime, please refer to [Azure Functions runtime versions overview](https://docs.microsoft.com/en-us/azure/azure-functions/functions-versions) page.

### What's available?

- Build, test, debug, and publish using Azure Functions Core Tools (CLI) or Visual Studio Code
- Deploy Python Function project onto consumption, dedicated, elastic premium, or flex consumption plan.
- Deploy Python Function project in a custom docker image onto dedicated or elastic premium plan.
- Triggers / Bindings : Blob, Cosmos DB, Event Grid, Event Hub, HTTP, Kafka, MySQL, Queue, ServiceBus, SQL, Timer, and Warmup
- Triggers / Bindings : Custom binding support

### What's new?

- [SDK Type Bindings for Blob](https://techcommunity.microsoft.com/t5/azure-compute-blog/azure-functions-sdk-type-bindings-for-azure-blob-storage-with/ba-p/4146744)
- [HTTP Streaming](https://techcommunity.microsoft.com/t5/azure-compute-blog/azure-functions-support-for-http-streams-in-python-is-now-in/ba-p/4146697)

### Get Started

- [Create your first Python function](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-first-function-python)
- [Developer guide](https://docs.microsoft.com/en-us/azure/azure-functions/functions-reference-python)
- [Binding API reference](https://docs.microsoft.com/en-us/python/api/azure-functions/azure.functions?view=azure-python)
- [Develop using VS Code](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-first-function-vs-code)
- [Create a Python Function on Linux using a custom docker image](https://docs.microsoft.com/en-us/azure/azure-functions/functions-create-function-linux-custom-image)

# Give Feedback

Issues and feature requests are tracked in a variety of places. To report this feedback, please file an issue to the relevant repository below:

| Item          | Description                                  | Link                                                                           |
|---------------|----------------------------------------------|--------------------------------------------------------------------------------|
| Python Worker | Programming Model, Triggers & Bindings       | [File an Issue](https://github.com/Azure/azure-functions-python-worker/issues) |
| Linux         | Base Docker Images                           | [File an Issue](https://github.com/Azure/azure-functions-docker/issues)        |
| Runtime       | Script Host & Language Extensibility         | [File an Issue](https://github.com/Azure/azure-functions-host/issues)          |
| VSCode        | VSCode Extension for Azure Functions         | [File an Issue](https://github.com/microsoft/vscode-azurefunctions/issues)     |
| Core Tools    | Command Line Interface for Local Development | [File an Issue](https://github.com/Azure/azure-functions-core-tools/issues)    |
| Portal        | User Interface or Experience Issue           | [File an Issue](https://github.com/azure/azure-functions-ux/issues)            |
| Templates     | Code Issues with Creation Template           | [File an Issue](https://github.com/Azure/azure-functions-templates/issues)     |

## Host configuration delivery

Classic, v1/v2 library, and R2P2 workers deliver `host.json` only when
`WorkerInitRequest.capabilities["HostConfiguration"]` is exactly `"1"`.
Other values omit the response field without reading the application root or
initializing a snapshot. The launcher must set `FUNCTIONS_APPLICATION_DIRECTORY`
in the worker environment; Python does not provision this variable or fall back
to the Host's `function_app_directory`, the worker directory, or the current
directory. Explicit relative roots retain native platform resolution.

The first enabled initialization captures an immutable, concurrency-safe
snapshot, including failures. Requested retries receive fresh envelopes with
the same snapshot; file changes are not reread. Existing placeholder
specialization invalidates the snapshot for the new application generation,
without introducing a reload response field. The independent distributions carry
identical package-local helpers (checked by a shared contract test), so library
runtimes and the protobuf-free R2P2 do not import the classic worker.

The payload is strictly decoded as UTF-8 by default, or UTF-8/UTF-16/UTF-32 with a
BOM, and incrementally converted to BOM-free UTF-8. Non-empty content is
normalized to strict compact JSON: `//` and `/* */` comments and trailing commas
are accepted and removed. String/property escapes, number spellings, duplicate
keys and key order are preserved without reserialization. Any single JSON root
is allowed, with at most 64 nested containers. Non-empty whitespace/comment-only
or malformed input produces `Error`; decoded empty files (including BOM-only
files) stay `Available` with empty content for the Host to reject.

The inclusive 65,536-byte cap applies both to converted bytes before parsing
and to normalized output, so oversized comments or malformed input cannot
evade the limit. A missing file at open in an accessible application directory
produces `Missing`; an invalid/unavailable root, read/close failure, encoding
error or invalid JSON produces `Error`; exceeding either limit produces
`TooLarge`. Only `Available` carries content. Each cached failure emits one
warning containing a fixed reason code, never paths, content or exception
details. Success, `Missing`, disabled calls and cache replays emit no delivery
warning. Initialization success/failure and app-setting precedence are unchanged;
the Host still owns configuration interpretation.

Normalization follows
[Azure/azure-functions-dotnet-worker#3522](https://github.com/Azure/azure-functions-dotnet-worker/pull/3522)
at commit `4c440d8d38526a16eb549ac6fba1082fe5ad4450`. Python uses strict decoders,
so legitimately encoded U+FFFD remains valid with or without a BOM; it does not
copy the reference's `StreamReader` replacement-character workaround.
Line comments end at CR, LF or EOF and reject U+2028/U+2029; those characters
remain valid in block comments and JSON strings, but not as JSON whitespace.

The field-6 `HostConfiguration` addition and comments are vendored from
[Azure/azure-functions-language-worker-protobuf#103](https://github.com/Azure/azure-functions-language-worker-protobuf/pull/103),
commit `313666583af4e97f0b534f1cbf61a3812f277c12`, without importing unrelated
upstream schema changes. The protocol is not yet a published release.
Regenerate classic/proxy bindings with `python -m invoke -c test_setup build-protos`
from `workers\tests` using the relevant interpreter (below 3.13 for classic,
3.13+ for proxy). That command recreates `workers\build`; preserve any existing
Host build before invoking it. R2P2's existing Cargo build generates prost
bindings from its vendored schema. Runtime test `FunctionRpc_pb2.py` fixtures
are generated with `grpc_tools.protoc --python_out` and the existing
`test_setup.make_absolute_imports` helper with `WORKER_DIR = "tests"`.

Proxy and R2P2 releases must consume v1/v2 runtime wheels containing this change.
In particular, the R2P2 packaging scripts currently download runtime versions
1.2.1 (v2) and 1.1.0 (v1), and their native-invocation overlays do not replace
initialization handlers. Publishing updated runtime packages and rolling their
pins forward is a release prerequisite; this change does not invent release
versions or patch older packages during a build. For source integration, use
the locally built runtime wheels or editable installs of both runtime folders.

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