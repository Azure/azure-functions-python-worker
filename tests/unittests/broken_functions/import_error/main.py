# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from sys import __nonexistent  # should raise ImportError


def main(req):
    __nonexistent()
