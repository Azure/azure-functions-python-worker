from __nonexistent import foo  # should raise ModuleNotFoundError


def main(req):
    foo()
