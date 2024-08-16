from azure.storage.blob import ContainerClient

# Clean up blobs
container_client = ContainerClient.from_connection_string(conn_str="AzureWebJobsStorage",
                                                          container_name="python-worker-tests")
blobs_list = container_client.list_blobs()
for blob in blobs_list:
    container_client.delete_blob(blob.name)
