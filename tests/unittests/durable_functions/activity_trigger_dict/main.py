# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Dict


def main(input: Dict[str, str]) -> Dict[str, str]:
    result = input.copy()
    if result.get('bird'):
        result['bird'] = result['bird'][::-1]

    return result
