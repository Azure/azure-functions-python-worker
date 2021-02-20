# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import random
import json
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.Out[bytes]) -> azf.HttpResponse:
    content_size = int(req.params['content_size'])

    content = bytearray(random.getrandbits(8) for _ in range(content_size))
    content_md5 = hashlib.md5(content).hexdigest()

    file.set(content)

    response_dict = {
        'content_size': content_size,
        'content_md5': content_md5
    }

    response_body = json.dumps(response_dict, indent=2)

    return azf.HttpResponse(
        body=response_body,
        mimetype="application/json",
        status_code=200
    )
