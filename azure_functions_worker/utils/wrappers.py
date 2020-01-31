from .common import is_envvar_true


def enable_feature_by(flag: str, default=None):
    def decorate(func):
        def call(*args, **kwargs):
            if is_envvar_true(flag):
                return func(*args, **kwargs)
        return call
    return decorate


def disable_feature_by(flag: str, default=None):
    def decorate(func):
        def call(*args, **kwargs):
            if not is_envvar_true(flag):
                return func(*args, **kwargs)
        return call
    return decorate
