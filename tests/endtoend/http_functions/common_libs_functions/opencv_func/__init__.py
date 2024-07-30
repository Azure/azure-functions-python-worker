# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging

import azure.functions as func
import cv2


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "opencv version: {}".format(cv2.__version__)

    return func.HttpResponse(res)
