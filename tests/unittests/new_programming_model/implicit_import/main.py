# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# Import simple module with implicit statement should now be acceptable
# since sys.path is now appended with function script root
from simple.main import main as s_main


def implicitinmport(req) -> str:
    return f's_main = {s_main(req)}'
