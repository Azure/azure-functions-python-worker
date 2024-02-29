# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func
import azure.functions.extension.blob as bindings

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.function_name(name="bc_blob_trigger")
@app.blob_trigger(arg_name="file",
                  path="python-worker-tests/test-blob-trigger.txt",
                  connection="AzureWebJobsStorage")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-blob-triggered.txt",
                 connection="AzureWebJobsStorage")
def bc_blob_trigger(client: bindings.BlobClient) -> str:
    blob_properties = client.get_blob_properties()
    file = client.download_blob(encoding='utf-8').readall()
    return json.dumps({
        'name': blob_properties.name,
        'length': blob_properties.size,
        'content': file
    })


@app.function_name(name="get_bc_blob_triggered")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-blob-triggered.txt",
                connection="AzureWebJobsStorage")
@app.route(route="get_blob_triggered")
def get_bc_blob_triggered(req: func.HttpRequest,
                          client: bindings.BlobClient) -> str:
    return client.download_blob(encoding='utf-8').readall()


@app.function_name(name="cc_blob_trigger")
@app.blob_trigger(arg_name="client",
                  path="python-worker-tests/test-blob-trigger.txt",
                  connection="AzureWebJobsStorage")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-blob-triggered.txt",
                 connection="AzureWebJobsStorage")
def cc_blob_trigger(client: bindings.ContainerClient) -> str:
    container_properties = client.get_container_properties()
    file = client.download_blob("test-blob-trigger.txt",
                                encoding='utf-8').readall()
    return json.dumps({
        'name': container_properties.name,
        'content': file
    })


@app.function_name(name="get_cc_blob_triggered")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-blob-triggered.txt",
                connection="AzureWebJobsStorage")
@app.route(route="get_blob_triggered")
def get_cc_blob_triggered(req: func.HttpRequest,
                          client: bindings.BlobClient) -> str:
    return client.download_blob("test-blob-trigger.txt",
                                encoding='utf-8').readall()


@app.function_name(name="ssd_blob_trigger")
@app.blob_trigger(arg_name="stream",
                  path="python-worker-tests/test-blob-trigger.txt",
                  connection="AzureWebJobsStorage")
@app.blob_output(arg_name="$return",
                 path="python-worker-tests/test-blob-triggered.txt",
                 connection="AzureWebJobsStorage")
def ssd_blob_trigger(stream: bindings.StorageStreamDownloader) -> str:
    file = stream.readall()
    return json.dumps({
        'content': file
    })


@app.function_name(name="get_ssd_blob_triggered")
@app.blob_input(arg_name="stream",
                path="python-worker-tests/test-blob-triggered.txt",
                connection="AzureWebJobsStorage")
@app.route(route="get_blob_triggered")
def get_ssd_blob_triggered(req: func.HttpRequest,
                           stream: bindings.BlobClient) -> str:
    return stream.readall()


@app.function_name(name="get_bc_bytes")
@app.route(route="get_bc_bytes")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-bytes.txt",
                connection="AzureWebJobsStorage")
def get_bc_bytes(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob(encoding='utf-8').readall()


@app.function_name(name="get_cc_bytes")
@app.route(route="get_cc_bytes")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-bytes.txt",
                connection="AzureWebJobsStorage")
def get_cc_bytes(req: func.HttpRequest,
                 client: bindings.ContainerClient) -> str:
    return client.download_blob("test-bytes.txt", encoding='utf-8').readall()


@app.function_name(name="get_ssd_bytes")
@app.route(route="get_ssd_bytes")
@app.blob_input(arg_name="stream",
                path="python-worker-tests/test-bytes.txt",
                connection="AzureWebJobsStorage")
def get_ssd_bytes(req: func.HttpRequest,
                  stream: bindings.StorageStreamDownloader) -> str:
    return stream.readall()


@app.function_name(name="get_bc_str")
@app.route(route="get_bc_str")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-str.txt",
                connection="AzureWebJobsStorage")
def get_bc_str(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob().readall()


@app.function_name(name="get_cc_str")
@app.route(route="get_cc_str")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-str.txt",
                connection="AzureWebJobsStorage")
def get_cc_str(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob("test-str.txt").readall()


@app.function_name(name="get_ssd_str")
@app.route(route="get_ssd_str")
@app.blob_input(arg_name="stream",
                path="python-worker-tests/test-str.txt",
                connection="AzureWebJobsStorage")
def get_ssd_str(req: func.HttpRequest, stream: bindings.BlobClient) -> str:
    return stream.readall()


@app.function_name(name="bc_and_inputstream_input")
@app.route(route="bc_and_inputstream_input")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-str.txt",
                data_type="STRING",
                connection="AzureWebJobsStorage")
@app.blob_input(arg_name="blob",
                path="python-worker-tests/test-str.txt",
                data_type="STRING",
                connection="AzureWebJobsStorage")
def bc_and_inputstream_input(req: func.HttpRequest, client: bindings.BlobClient,
                             blob: func.InputStream) -> str:
    output_msg = ""
    file = blob.read().decode('utf-8')
    client_file = client.download_blob().readall()
    output_msg = file + " - input stream " + client_file + " - blob client"
    return output_msg


@app.function_name(name="type_undefined")
@app.route(route="type_undefined")
@app.blob_input(arg_name="file",
                path="python-worker-tests/test-bytes.txt",
                data_type="BINARY",
                connection="AzureWebJobsStorage")
def type_undefined(req: func.HttpRequest, file) -> str:
    assert not isinstance(file, bindings.BlobClient)
    assert not isinstance(file, bindings.ContainerClient)
    assert not isinstance(file, bindings.StorageStreamDownloader)
    return file.decode('utf-8')


@app.function_name(name="bc_cache")
@app.route(route="bc_cache")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-str.txt",
                data_type="STRING",
                connection="AzureWebJobsStorage")
def bc_cache(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob().readall()


@app.function_name(name="bc_cache_2")
@app.route(route="bc_cache_2")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-bytes.txt",
                data_type="BINARY",
                connection="AzureWebJobsStorage")
def bc_cache_2(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob().readall()


@app.function_name(name="bc_cache_3")
@app.route(route="bc_cache_3")
@app.blob_input(arg_name="client",
                path="python-worker-tests/test-str.txt",
                data_type="STRING",
                connection="AzureWebJobsStorage")
def bc_cache_3(req: func.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob().readall()


@app.function_name(name="put_blob_str2")
@app.blob_output(arg_name="file",
                 path="python-worker-tests/test-str.txt",
                 connection="AzureWebJobsStorage")
@app.route(route="put_blob_str2")
def put_blob_str2(req: func.HttpRequest, file: func.Out[str]) -> str:
    file.set(req.get_body())
    return 'OK'


@app.function_name(name="put_blob_trigger")
@app.blob_output(arg_name="file",
                 path="python-worker-tests/test-blob-trigger.txt",
                 connection="AzureWebJobsStorage")
@app.route(route="put_blob_trigger")
def put_blob_trigger(req: func.HttpRequest, file: func.Out[str]) -> str:
    file.set(req.get_body())
    return 'OK'
