# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from __nonexistent import foo  # should raise ModuleNotFoundError


def main(req):
    foo()
