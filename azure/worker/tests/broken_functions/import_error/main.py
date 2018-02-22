from sys import __nonexistent  # should raise ImportError


def main(req):
    __nonexistent()
