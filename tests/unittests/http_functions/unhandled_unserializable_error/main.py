# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import azure.functions as func


class UnserializableException(Exception):
    def __str__(self):
        raise RuntimeError('cannot serialize me')


def main(req: func.HttpRequest) -> str:
    raise UnserializableException('foo')
