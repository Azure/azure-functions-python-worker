# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import List


# This is testing the function load feature for the multiple events annotation
# The event shouldn't be List[str]
def main(events: List[str]) -> str:
    return 'BAD'
