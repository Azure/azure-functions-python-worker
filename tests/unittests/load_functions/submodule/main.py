from .sub_module import module


def main(req) -> str:
    return module.__name__
