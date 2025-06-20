# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(docs: azf.DocumentList) -> str:
    return docs[0].to_json()
