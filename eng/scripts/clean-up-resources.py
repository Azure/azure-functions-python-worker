from azure.storage.blob import ContainerClient
from azure.cosmos import CosmosClient

# Clean up Blob storage account
container_client = ContainerClient.from_connection_string(
    conn_str="AzureWebJobsStorage",
    container_name="python-worker-tests")
for blob in container_client.list_blobs():
    container_client.delete_blob(blob.name)

# Clean up CosmosDB
cosmos_client = CosmosClient.from_connection_string(
    conn_str="AzureWebJobsCosmosDBConnectionString")
database = cosmos_client.get_database_client("test")
container = database.get_container_client("items")
for item in container.query_items(
        query='SELECT * FROM items',
        enable_cross_partition_query=True):
    container.delete_item(item, partition_key='Widget')
