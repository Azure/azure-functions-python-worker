# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import re


class InvalidFileNameError(Exception):

    def __init__(self, file_name: str) -> None:
        super().__init__(
            'Invalid file name: %s', file_name)


def validate_script_file_name(file_name: str):
    # First character can be a letter, number, or underscore
    # Following characters can be a letter, number, underscore, hyphen, or dash
    # Ending must be .py
    pattern = re.compile(r'^[a-zA-Z0-9_][a-zA-Z0-9_\-]*\.py$')
    if not pattern.match(file_name):
        raise InvalidFileNameError(file_name)
