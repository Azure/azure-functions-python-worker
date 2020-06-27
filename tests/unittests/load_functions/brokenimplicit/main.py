# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# Import simple module with implicit directory import statement should fail
from simple.main import main as s_main


def brokenimplicit(req) -> str:
    return f's_main = {s_main(req)}'
