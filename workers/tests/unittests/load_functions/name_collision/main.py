# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# Both customer code and third-party package has the same name pytest.
# Worker should pick the pytest from the third-party package
import pytest as pt


def main(req) -> str:
    return f'pt.__version__ = {pt.__version__}'
