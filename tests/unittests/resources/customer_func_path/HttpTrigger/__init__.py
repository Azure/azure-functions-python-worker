# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os

import azure.functions as func  # NoQA


def main():
    return os.path.abspath(os.path.dirname(func.__file__))
