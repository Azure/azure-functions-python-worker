# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# Import simple module with implicit statement should now be acceptable
import notfound


def modulenotfound(req) -> str:
    return f'notfound = {notfound.__name__}'
