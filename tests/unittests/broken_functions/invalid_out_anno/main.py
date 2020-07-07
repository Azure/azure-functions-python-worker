# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as azf


def main(req, ret: azf.Out[azf.HttpRequest]):
    return 'trust me, it is OK!'
