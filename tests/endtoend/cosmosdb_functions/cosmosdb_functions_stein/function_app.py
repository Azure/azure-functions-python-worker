# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route()
@app.cosmos_db_input(
    arg_name="docs",
    database_name="test",
    container_name="items",
    id="cosmosdb-input-test",
    connection="AzureWebJobsCosmosDBConnectionString",
)
def cosmosdb_input(req: func.HttpRequest, docs: func.DocumentList) -> str:
    return func.HttpResponse(docs[0].to_json(), mimetype="application/json")


@app.cosmos_db_trigger(
    arg_name="docs",
    database_name="test",
    container_name="items",
    lease_container_name="leases",
    connection="AzureWebJobsCosmosDBConnectionString",
    create_lease_container_if_not_exists=True,
)
@app.blob_output(
    arg_name="$return",
    connection="AzureWebJobsStorage",
    path="python-worker-tests/test-cosmosdb-triggered.txt",
)
def cosmosdb_trigger(docs: func.DocumentList) -> str:
    return docs[0].to_json()


@app.route()
@app.blob_input(
    arg_name="file",
    connection="AzureWebJobsStorage",
    path="python-worker-tests/test-cosmosdb-triggered.txt",
)
def get_cosmosdb_triggered(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode("utf-8")


@app.route()
@app.cosmos_db_output(
    arg_name="doc",
    database_name="test",
    container_name="items",
    create_if_not_exists=True,
    connection="AzureWebJobsCosmosDBConnectionString",
)
def put_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    doc.set(func.Document.from_json(req.get_body()))
    return "OK"
