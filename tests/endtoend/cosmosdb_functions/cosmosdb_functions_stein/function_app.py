# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func

app = func.FunctionApp()


@app.route()
@app.read_cosmos_db_documents(
    arg_name="docs", database_name="test",
    collection_name="items",
    id="cosmosdb-input-test",
    connection_string_setting="AzureWebJobsCosmosDBConnectionString")
def cosmosdb_input(req: func.HttpRequest, docs: func.DocumentList) -> str:
    return func.HttpResponse(docs[0].to_json(), mimetype='application/json')


@app.cosmos_db_trigger(
    arg_name="docs", database_name="test",
    collection_name="items",
    lease_collection_name="leases",
    connection_string_setting="AzureWebJobsCosmosDBConnectionString",
    create_lease_collection_if_not_exists=True)
@app.write_blob(arg_name="$return", connection="AzureWebJobsStorage",
                path="python-worker-tests/test-cosmosdb-triggered.txt")
def cosmosdb_trigger(docs: func.DocumentList) -> str:
    return docs[0].to_json()


@app.route()
@app.read_blob(arg_name="file", connection="AzureWebJobsStorage",
               path="python-worker-tests/test-cosmosdb-triggered.txt")
def get_cosmosdb_triggered(req: func.HttpRequest,
                           file: func.InputStream) -> str:
    return file.read().decode('utf-8')


@app.route()
@app.write_cosmos_db_documents(
    arg_name="doc", database_name="test",
    collection_name="items",
    create_if_not_exists=True,
    connection_string_setting="AzureWebJobsCosmosDBConnectionString")
def put_document(req: func.HttpRequest, doc: func.Out[func.Document]):
    doc.set(func.Document.from_json(req.get_body()))

    return 'OK'
