# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

_EXTENSIONS_CONTEXT = dict()


def register_before_invocation_request(callback):
    if _EXTENSIONS_CONTEXT.get("BEFORE_INVOCATION_REQUEST_CALLBACKS"):
        _EXTENSIONS_CONTEXT.get(
            "BEFORE_INVOCATION_REQUEST_CALLBACKS").append(callback)
    else:
        _EXTENSIONS_CONTEXT["BEFORE_INVOCATION_REQUEST_CALLBACKS"] = [callback]
    _EXTENSIONS_CONTEXT["BEFORE_INVOCATION_REQUEST_CALLBACKS"] = [callback]


def register_after_invocation_request(callback):
    if _EXTENSIONS_CONTEXT.get("AFTER_INVOCATION_REQUEST_CALLBACKS"):
        _EXTENSIONS_CONTEXT.get(
            "AFTER_INVOCATION_REQUEST_CALLBACKS").append(callback)
    else:
        _EXTENSIONS_CONTEXT["AFTER_INVOCATION_REQUEST_CALLBACKS"] = [callback]


def clear_before_invocation_request_callbacks():
    _EXTENSIONS_CONTEXT.pop("BEFORE_INVOCATION_REQUEST_CALLBACKS", None)


def clear_after_invocation_request_callbacks():
    _EXTENSIONS_CONTEXT.pop("AFTER_INVOCATION_REQUEST_CALLBACKS", None)


def get_before_invocation_request_callbacks():
    return _EXTENSIONS_CONTEXT.get("BEFORE_INVOCATION_REQUEST_CALLBACKS", [])


def get_after_invocation_request_callbacks():
    return _EXTENSIONS_CONTEXT.get("AFTER_INVOCATION_REQUEST_CALLBACKS", [])
