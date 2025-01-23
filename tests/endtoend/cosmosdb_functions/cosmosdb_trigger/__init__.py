# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(docs_snake: azf.DocumentList) -> str:
    return docs_snake[0].to_json()
