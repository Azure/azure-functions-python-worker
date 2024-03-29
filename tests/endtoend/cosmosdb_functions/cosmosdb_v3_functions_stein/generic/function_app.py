# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp()


@app.generic_trigger(arg_name="req", type="httpTrigger")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="docs",
    type="cosmosDB",
    database_name="test",
    collection_name="items",
    id="cosmosdb-input-test",
    connection_string_setting="AzureWebJobsCosmosDBConnectionString")
def cosmosdb_input(req: func.HttpRequest, docs: func.DocumentList) -> str:
    return func.HttpResponse(docs[0].to_json(), mimetype='application/json')


@app.generic_trigger(
    arg_name="docs",
    type="cosmosDBTrigger",
    database_name="test",
    collection_name="items",
    lease_collection_name="leases",
    connection_string_setting="AzureWebJobsCosmosDBConnectionString",
    create_lease_collection_if_not_exists=True)
@app.generic_output_binding(
    arg_name="$return",
    type="blob",
    connection="AzureWebJobsStorage",
    path="python-worker-tests/test-cosmosdb-triggered.txt")
def cosmosdb_trigger(docs: func.DocumentList) -> str:
    return docs[0].to_json()


@app.generic_trigger(arg_name="req", type="httpTrigger")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_input_binding(
    arg_name="file",
    connection="AzureWebJobsStorage",
    type="blob",
    path="python-worker-tests/test-cosmosdb-triggered.txt")
def get_cosmosdb_triggered(req: func.HttpRequest,
                           file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.generic_trigger(arg_name="req", type="httpTrigger")
@app.generic_output_binding(arg_name="$return", type="http")
@app.generic_output_binding(
    arg_name="doc",
    database_name="test",
    type="cosmosDB",
    collection_name="items",
    create_if_not_exists=True,
    connection_string_setting="AzureWebJobsCosmosDBConnectionString")
def put_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    doc.set(func.Document.from_json(req.get_body()))

    return 'OK'
