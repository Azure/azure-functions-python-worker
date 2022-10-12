# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import cv2
import azure.functions as func


def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    img = cv2.imread("test.png", cv2.IMREAD_COLOR)
    res = "shape of image: {}".format(img.shape)

    return func.HttpResponse(res)
