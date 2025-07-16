# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# Retrieve the event data from storage blob and return it as Http response
def main(req: func.HttpRequest, file: func.InputStream) -> str:
    return file.read().decode('utf-8')
