# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import numpy as np
from pandas import DataFrame


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    array = np.arange(6).reshape(3, 2)
    df = DataFrame(array, columns=['x', 'y'], index=['T1', 'T2', 'T3'])

    res = "two-dimensional DataFrame: \n {}".format(df)

    return func.HttpResponse(res)
