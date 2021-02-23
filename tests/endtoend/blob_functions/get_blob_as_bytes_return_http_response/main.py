# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: bytes) -> azf.HttpResponse:
    """
    Read a blob (bytes) and respond back (in HTTP response) with the number of
    bytes read and the MD5 digest of the content.
    """
    assert isinstance(file, bytes)

    content_size = len(file)
    content_md5 = hashlib.md5(file).hexdigest()

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
