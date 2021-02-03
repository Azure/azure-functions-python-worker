# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

from typing import NamedTuple, Callable, List, Dict


# Mock azure.functions provides customer with FuncExtension
class FuncExtensionHookMeta(NamedTuple):
    ext_name: str
    impl: Callable


# Defines kinds of hook that we support
class FuncExtensionHooks(NamedTuple):
    before_invocation: List[FuncExtensionHookMeta] = []
    after_invocation: List[FuncExtensionHookMeta] = []


class MockExtension:
    before_invocation_context = None
    after_invocation_context = None

    @classmethod
    def before_invocation(cls, logger, context, *args, **kwargs):
        cls.before_invocation_context = context
        logger.info(f'executed at {context.function_name}')

    @classmethod
    def after_invocation(cls, logger, context, *args, **kwargs):
        cls.after_invocation_context = context
        logger.warning(f'failed at {context.function_name}')
        raise Exception(f'threw exception from {context.function_name}')


class FuncExtension:
    _instances: Dict[str, FuncExtensionHooks] = {
        'httptrigger': FuncExtensionHooks(
            before_invocation=[
                FuncExtensionHookMeta(
                    ext_name='MockExtension',
                    impl=MockExtension.before_invocation
                )
            ],
            after_invocation=[
                FuncExtensionHookMeta(
                    ext_name='MockExtension',
                    impl=MockExtension.after_invocation
                )
            ]
        )
    }

    def __init__(self, trigger_name: str):
        self.trigger_name = trigger_name

    @classmethod
    def get_hooks_of_trigger(cls, trigger_name: str) -> FuncExtensionHooks:
        return cls._instances.get(trigger_name.lower(), FuncExtensionHooks())

    def before_invocation(self, logger, context, *args, **kwargs):
        pass

    def after_invocation(self, logger, context, *args, **kwargs):
        pass



MESSAGE = "This is a mocked azure.functions package (with sdk)"

__version__ = "1.7.0"

__all__ = [
    'FuncExtension',
    'FuncExtensionHooks',
    'FuncExtensionHookMeta',
    'MockExtension'
]
