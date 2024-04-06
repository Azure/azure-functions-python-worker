# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# Retrieve the event data from storage blob and return it as Http response
def main(req: func.HttpRequest, testEntities: func.InputStream):
    return func.HttpResponse(status_code=200,
                             body=testEntities.read().decode('utf-8'))
