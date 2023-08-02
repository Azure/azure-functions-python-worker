# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import azure.functions as func
import logging

app = func.FunctionApp()


@app.warm_up_trigger('warmup')
def warmup(warmup) -> None:
    logging.info('Function App instance is warm')
