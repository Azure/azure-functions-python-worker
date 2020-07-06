# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions


def main(req: azure.functions.HttpRequest):
    flush_required = False
    if req.params.get('flush') == 'true':
        flush_required = True

    print('The quick brown fox prints on the lazy dog', flush=flush_required)
    return 'OK-print-logging'
