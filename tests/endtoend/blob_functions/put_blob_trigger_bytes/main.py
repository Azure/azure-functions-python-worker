# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import random
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.Out[bytes]) -> azf.HttpResponse:
    """
    Write a blob (bytes) and respond back (in HTTP response) with the number of
    bytes written and the MD5 digest of the content.
    The number of bytes to write are specified in the input HTTP request.
    This function's output blob triggers another function: blob_trigger_bytes
    """
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
