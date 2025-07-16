# This function app is to ensure the code outside main() function
# should only get loaded once in __init__.py

_INVOCATION_COUNT: int = 0


def invoke():
    global _INVOCATION_COUNT
    _INVOCATION_COUNT += 1


def get_invoke_count() -> int:
    global _INVOCATION_COUNT
    return _INVOCATION_COUNT


def reset_count():
    global _INVOCATION_COUNT
    _INVOCATION_COUNT = 0
