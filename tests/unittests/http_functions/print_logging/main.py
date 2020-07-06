# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import sys
import azure.functions


def main(req: azure.functions.HttpRequest):
    flush_required = False
    is_console_log = False
    is_stderr = False
    message = req.params.get('message', '')

    if req.params.get('flush') == 'true':
        flush_required = True
    if req.params.get('console') == 'true':
        is_console_log = True
    if req.params.get('is_stderr') == 'true':
        is_stderr = True

    # Adding LanguageWorkerConsoleLog will make function host to treat
    # this as system log and will be propagated to kusto
    prefix = 'LanguageWorkerConsoleLog' if is_console_log else ''
    print(f'{prefix} {message}'.strip(),
          file=sys.stderr if is_stderr else sys.stdout,
          flush=flush_required)

    return 'OK-print-logging'
