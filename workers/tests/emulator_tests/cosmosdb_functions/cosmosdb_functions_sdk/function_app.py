# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import logging

import azure.functions as func
import azurefunctions.extensions.bindings.cosmosdb as cosmos

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="cosmos")
@app.cosmos_db_input(
    arg_name="client",
    connection="AzureWebJobsCosmosDBConnectionString",
    database_name=None,
    container_name=None)
def cosmos_client_input(req: func.HttpRequest,
                        client: cosmos.CosmosClient) -> str:
    databases = client.list_databases()
    for database in databases:
        logging.info("Found database with ID: %s", database.get('id'))

    return 'ok'


@app.route(route="container")
@app.cosmos_db_input(
    arg_name="container",
    connection="AzureWebJobsCosmosDBConnectionString",
    database_name="test",
    container_name="items")
def container_proxy_input(req: func.HttpRequest,
                          container: cosmos.ContainerProxy) -> str:
    documents = container.query_items(
        query="SELECT * FROM c",
        enable_cross_partition_query=True)
    for document in documents:
        logging.info("Found document: %s", document)

    return 'ok'


@app.route(route="database")
@app.cosmos_db_input(
    arg_name="database",
    connection="AzureWebJobsCosmosDBConnectionString",
    database_name="test",
    container_name=None)
def database_proxy_input(req: func.HttpRequest,
                         database: cosmos.DatabaseProxy) -> str:
    containers = database.list_containers()
    for container in containers:
        logging.info("Found container with ID: %s", container.get('id'))

    return 'ok'
