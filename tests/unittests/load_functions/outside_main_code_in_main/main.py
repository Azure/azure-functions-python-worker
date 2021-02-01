# This function app is to ensure the code outside main() function
# should only get loaded once in __init__.py

from .count import invoke, get_invoke_count, reset_count


invoke()


def main(req):
    count = get_invoke_count()
    reset_count()
    return f'executed count = {count}'
