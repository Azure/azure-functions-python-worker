# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


def main(req: func.HttpRequest, doc: func.Out[func.Document]):
    doc.set(func.Document.from_json(req.get_body()))

    return 'OK'
