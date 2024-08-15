# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from .sub_module import module


def main(req) -> str:
    return module.__name__
