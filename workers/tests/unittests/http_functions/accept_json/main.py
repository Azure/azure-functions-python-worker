# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json

import azure.functions


def main(req: azure.functions.HttpRequest):
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': dict(req.params),
        'get_body': req.get_body().decode(),
        'get_json': req.get_json()
    })
