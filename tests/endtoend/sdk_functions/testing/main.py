# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf
import azure.functions.extension.blob as bindings


def main(req: azf.HttpRequest, client: bindings.BlobClient) -> str:
    return client.download_blob(encoding='utf-8').readall()
