# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import random
import json
import hashlib
import azure.functions as azf


def _generate_content_and_digest(content_size):
    content = bytearray(random.getrandbits(8) for _ in range(content_size))
    content_md5 = hashlib.md5(content).hexdigest()
    return content, content_md5


def main(
        req: azf.HttpRequest,
        inputfile1: bytes,
        inputfile2: bytes,
        outputfile1: azf.Out[bytes],
        outputfile2: azf.Out[bytes]) -> azf.HttpResponse:
    """
    Read two blobs (bytes) and respond back (in HTTP response) with the number
    of bytes read from each blob and the MD5 digest of the content of each.
    Write two blobs (bytes) and respond back (in HTTP response) with the number
    bytes written in each blob and the MD5 digest of the content of each.
    The number of bytes to write are specified in the input HTTP request.
    """
    input_content_size_1 = len(inputfile1)
    input_content_size_2 = len(inputfile2)

    input_content_md5_1 = hashlib.md5(inputfile1).hexdigest()
    input_content_md5_2 = hashlib.md5(inputfile2).hexdigest()

    output_content_size_1 = int(req.params['output_content_size_1'])
    output_content_size_2 = int(req.params['output_content_size_2'])

    output_content_1, output_content_md5_1 = \
        _generate_content_and_digest(output_content_size_1)
    output_content_2, output_content_md5_2 = \
        _generate_content_and_digest(output_content_size_2)

    outputfile1.set(output_content_1)
    outputfile2.set(output_content_2)

    response_dict = {
        'input_content_size_1': input_content_size_1,
        'input_content_size_2': input_content_size_2,
        'input_content_md5_1': input_content_md5_1,
        'input_content_md5_2': input_content_md5_2,
        'output_content_size_1': output_content_size_1,
        'output_content_size_2': output_content_size_2,
        'output_content_md5_1': output_content_md5_1,
        'output_content_md5_2': output_content_md5_2
    }

    response_body = json.dumps(response_dict, indent=2)

    return azf.HttpResponse(
        body=response_body,
        mimetype="application/json",
        status_code=200
    )
