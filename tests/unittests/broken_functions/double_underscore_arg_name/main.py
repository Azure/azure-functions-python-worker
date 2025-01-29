# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(__req: azf.HttpRequest):
    return azf.HttpResponse('<h1>Hello World™</h1>',
                            mimetype='text/html')
