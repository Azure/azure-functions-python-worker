"""Python functions loader."""


import importlib
import os.path
import sys


def load_function(name: str, directory: str, script_file: str):
    # TODO: Implement an importlib.Finder instead of injecting
    # paths into sys.path.

    if not os.path.isfile(script_file):
        raise RuntimeError(
            f'cannot load function {name}: '
            f'script file does not exist {script_file}')

    path_entry = os.path.dirname(directory)
    filename = os.path.basename(script_file)
    modname, ext = os.path.splitext(filename)
    if ext != '.py':
        raise RuntimeError(
            f'cannot load function {name}: '
            f'invalid Python filename {script_file}')

    if path_entry not in sys.path:
        sys.path.append(path_entry)

    try:
        mod = importlib.import_module(f'{name}.{modname}')
    except ImportError as ex:
        raise RuntimeError(
            f'could not import module for function {name}') from ex

    func = getattr(mod, 'main', None)
    if func is None or not callable(func):
        raise ImportError(
            f'cannot load function {name}: no main() function in '
            f'{filename!r} file')

    return func
