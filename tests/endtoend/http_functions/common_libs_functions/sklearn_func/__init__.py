# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import azure.functions as func
from sklearn.datasets import load_iris


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    iris = load_iris()

    res = "First 5 records of array: \n {}".format(iris.data[:5])

    return func.HttpResponse(res)
