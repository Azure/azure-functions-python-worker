from .common import is_envvar_true
from .tracing import extend_exception_message


def enable_feature_by(flag: str, default=None):
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return func(*args, **kwargs)
            return default
        return call
    return decorate


def disable_feature_by(flag: str, default=None):
    def decorate(func):
        def call(*args, **kwargs):
            if not is_envvar_true(flag):
                return func(*args, **kwargs)
            return default
        return call
    return decorate


def attach_message_to_exception(expt_type: Exception, message: str):
    def decorate(func):
        def call(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except expt_type as e:
                raise extend_exception_message(e, message)
        return call
    return decorate
