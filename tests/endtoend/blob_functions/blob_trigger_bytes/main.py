# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import json
import hashlib


def main(file: bytes) -> str:
    """
    Reads an input file (bytes) and writes the number of bytes read and the MD5
    digest of the read content into an output file, in JSON format.
    """
    content_size = len(file)
    content_md5 = hashlib.md5(file).hexdigest()

    output_content = {
        'content_size': content_size,
        'content_md5': content_md5
    }

    output_json = json.dumps(output_content)
    return output_json
