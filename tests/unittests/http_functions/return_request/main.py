# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import json
import hashlib

import azure.functions


def main(req: azure.functions.HttpRequest):
    params = dict(req.params)
    params.pop('code', None)
    body = req.get_body()
    return json.dumps({
        'method': req.method,
        'url': req.url,
        'headers': dict(req.headers),
        'params': params,
        'get_body': body.decode(),
        'body_hash': hashlib.sha256(body).hexdigest(),
    })
