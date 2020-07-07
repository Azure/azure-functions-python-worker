# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req: azf.HttpRequest, foo: azf.Out[azf.HttpResponse]):
    foo.set(azf.HttpResponse(body='hello', status_code=201))
