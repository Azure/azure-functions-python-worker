# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest, testEntity_snake):
    return func.HttpResponse(status_code=200, body=testEntity_snake)
