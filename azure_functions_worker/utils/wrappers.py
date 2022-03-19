# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
from typing import Any, Callable

from .common import is_envvar_false, is_envvar_true
from .tracing import extend_exception_message


def enable_feature_by(
    flag: str, default: Any = None, flag_default: bool = False
) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return func(*args, **kwargs)
            if flag_default and not is_envvar_false(flag):
                return func(*args, **kwargs)
            return default

        return call

    return decorate


def disable_feature_by(
    flag: str, default: Any = None, flag_default: bool = False
) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return default
            if flag_default and not is_envvar_false(flag):
                return default
            return func(*args, **kwargs)

        return call

    return decorate


def attach_message_to_exception(expt_type: Exception, message: str) -> Callable:
    def decorate(func):
        def call(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except expt_type as e:
                raise extend_exception_message(e, message)

        return call

    return decorate
