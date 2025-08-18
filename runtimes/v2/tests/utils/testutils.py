# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unittest helpers.

All functions in this file should be considered private APIs,
and can be changed without a notice.
"""

import asyncio
import functools
import inspect
import unittest


class AsyncTestCaseMeta(type(unittest.TestCase)):
    def __new__(mcls, name, bases, ns):
        for attrname, attr in ns.items():
            if (attrname.startswith('test_')
                    and inspect.iscoroutinefunction(attr)):
                ns[attrname] = mcls._sync_wrap(attr)

        return super().__new__(mcls, name, bases, ns)

    @staticmethod
    def _sync_wrap(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return asyncio.run(func(*args, **kwargs))

        return wrapper


class AsyncTestCase(unittest.TestCase, metaclass=AsyncTestCaseMeta):
    pass
