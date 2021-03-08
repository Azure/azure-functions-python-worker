# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: azf.InputStream) -> azf.HttpResponse:
    """
    Read a blob (as azf.InputStream) and respond back (in HTTP response) with
    the number of bytes read and the MD5 digest of the content.
    """
    file_bytes = file.read()

    content_size = len(file_bytes)
    content_md5 = hashlib.md5(file_bytes).hexdigest()

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
