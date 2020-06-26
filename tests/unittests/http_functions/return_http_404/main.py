# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest):
    return azf.HttpResponse('bye', status_code=404)
