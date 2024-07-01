# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import logging
import azure.functions as func
import numpy as np
import requests
import cv2
from pandas import DataFrame
from sklearn.datasets import load_iris
import plotly
import dotenv


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="dotenv_func")
def dotenv_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "found" if "load_dotenv" in dotenv.__all__ else "not found"

    return func.HttpResponse(res)


@app.route(route="numpy_func")
def numpy_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "numpy version: {}".format(np.__version__)

    return func.HttpResponse(res)


@app.route(route="opencv_func")
def opencv_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "opencv version: {}".format(cv2.__version__)

    return func.HttpResponse(res)


@app.route(route="pandas_func")
def pandas_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    array = np.arange(6).reshape(3, 2)
    df = DataFrame(array, columns=['x', 'y'], index=['T1', 'T2', 'T3'])

    res = "two-dimensional DataFrame: \n {}".format(df)

    return func.HttpResponse(res)


@app.route(route="plotly_func")
def plotly_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    res = "plotly version: {}".format(plotly.__version__)

    return func.HttpResponse(res)


@app.route(route="requests_func")
def requests_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    req = requests.get('https://github.com')
    res = "req status code: {}".format(req.status_code)

    return func.HttpResponse(res)


@app.route(route="sklearn_func")
def sklearn_func(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    iris = load_iris()

    res = "First 5 records of array: \n {}".format(iris.data[:5])

    return func.HttpResponse(res)
