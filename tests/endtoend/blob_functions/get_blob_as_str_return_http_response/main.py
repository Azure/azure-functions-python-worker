# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib
import azure.functions as azf


def main(req: azf.HttpRequest, file: str) -> azf.HttpResponse:
    """
    Read a blob (string) and respond back (in HTTP response) with the number of
    characters read and the MD5 digest of the utf-8 encoded content.
    """
    assert isinstance(file, str)

    num_chars = len(file)
    content_bytes = file.encode('utf-8')
    content_md5 = hashlib.md5(content_bytes).hexdigest()

    response_dict = {
        'num_chars': num_chars,
        'content_md5': content_md5
    }

    response_body = json.dumps(response_dict, indent=2)

    return azf.HttpResponse(
        body=response_body,
        mimetype="application/json",
        status_code=200
    )
