# Azure Functions Python Runtime — Architecture Atlas (`docs/site`)

Interactive GitHub Pages site documenting the Azure Functions Python runtime architecture across:

- **5 Linked Repositories**:
  - [`Azure/azure-functions-host`](https://github.com/Azure/azure-functions-host) (.NET Script Host runtime)
  - [`Azure/azure-functions-language-worker-protobuf`](https://github.com/Azure/azure-functions-language-worker-protobuf) (Host ↔ Worker `.proto` contract)
  - [`Azure/azure-functions-python-worker`](https://github.com/Azure/azure-functions-python-worker) (Worker shells + V1/V2 runtimes)
  - [`Azure/azure-functions-python-library`](https://github.com/Azure/azure-functions-python-library) (`azure-functions` SDK)
  - [`Azure/azure-functions-python-extensions`](https://github.com/Azure/azure-functions-python-extensions) (HTTP v2, `SdkType` bindings, Agent runtimes)
- **3 Worker Generations**: Python `≤ 3.12` (`workers/azure_functions_worker`), Python `3.13–3.14` (`workers/proxy_worker` + `runtimes/`), and Python `3.15+` (`workers/r2p2` + `PyO3` + `runtimes/`).
- **7 Lifecycle Phases per Generation**: Worker Init, Specialization (Consumption), Metadata & Indexing, Functions Load (V1), Invocation, Worker Status, and Worker Logs (`RpcLog`).

## Local Preview

```bash
python3 eng/docs/extract_arch.py
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs/site
```

Then open `http://127.0.0.1:8765/`.

## GitHub Pages Setup

`.github/workflows/architecture-pages.yml` builds and validates the site on pull requests and deploys to `https://azure.github.io/azure-functions-python-worker/` on `dev`. Ensure **Settings → Pages → Build and deployment → Source** is set to **GitHub Actions**.
