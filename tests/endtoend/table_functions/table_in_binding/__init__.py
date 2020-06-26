# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions as func


def main(req: func.HttpRequest, testEntity):
    headers_dict = json.loads(testEntity)
    return func.HttpResponse(status_code=200, headers=headers_dict)
