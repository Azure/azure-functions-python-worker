# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func
import azure.functions.extension.blob as bindings

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="get_bc_blob_triggered")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-blobclient-triggered.txt",
                connection="AzureWebJobsStorage")
@app.route(route="get_bc_blob_triggered")
def get_bc_blob_triggered(req: func.HttpRequest,
                          client: bindings.BlobClient) -> str:
    return client.download_blob(encoding='utf-8').readall()


@app.function_name(name="blob_trigger")
@app.blob_trigger(arg_name="file",
                  path="python-worker-tests/test-blob-trigger.txt",
                  connection="AzureWebJobsStorage")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-blob-triggered.txt",
                 connection="AzureWebJobsStorage")
def blob_trigger(file: func.InputStream) -> str:
    return json.dumps({
        'name': file.name,
        'length': file.length,
        'content': file.read().decode('utf-8')
    })
