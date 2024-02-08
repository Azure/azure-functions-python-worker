# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


# There are 3 bindings defined in function.json:
# 1. req: HTTP trigger
# 2. testEntities: table input (generic)
# 3. $return: HTTP response
# The bindings will be processed by the worker in this order:
# req -> $return -> testEntities
def main(req: func.HttpRequest, testEntities):
    return func.HttpResponse(status_code=200)
