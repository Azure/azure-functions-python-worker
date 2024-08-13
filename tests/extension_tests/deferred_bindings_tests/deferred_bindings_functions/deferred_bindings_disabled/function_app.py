# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="blob_trigger_only")
@app.blob_trigger(arg_name="file",
                  path="python-worker-tests/test-blob-trigger.txt",
                  connection="AzureWebJobsStorage")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-blob-triggered.txt",
                 connection="AzureWebJobsStorage")
def blob_trigger_only(file: func.InputStream) -> str:
    return json.dumps({
        'name': file.name,
        'length': file.length,
        'content': file.read().decode('utf-8')
    })
