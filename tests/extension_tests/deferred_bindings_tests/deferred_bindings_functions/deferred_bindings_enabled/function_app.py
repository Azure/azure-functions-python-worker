# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func
import azurefunctions.extensions.bindings.blob as blob

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="blob_input_only")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-blobclient-triggered.txt",
                connection="AzureWebJobsStorage")
@app.route(route="blob_input_only")
def blob_input_only(req: func.HttpRequest,
                    client: blob.BlobClient) -> str:
    return client.download_blob(encoding='utf-8').readall()
