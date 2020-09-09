# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

# Both customer code and third-party package has the same name pytest.
# When using absolute import, should pick customer's package.
import __app__.pytest as pt


def main(req) -> str:
    return f'pt.__version__ = {pt.__version__}'
