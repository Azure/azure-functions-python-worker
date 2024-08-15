# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.


def main(req):
    # This function will fail, as we don't auto-convert "bytes" to "http".
    return b'Hello World!'
