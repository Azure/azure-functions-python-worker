"""Python functions loader."""


import importlib
import importlib.machinery
import importlib.util
import os
import os.path
import pathlib
import sys
import typing


_AZURE_NAMESPACE = '__azure__'

_submodule_dirs = []


def register_function_dir(path: os.PathLike):
    _submodule_dirs.append(os.fspath(path))


def install():
    if _AZURE_NAMESPACE not in sys.modules:
        # Create and register the __azure__ namespace package.
        ns_spec = importlib.machinery.ModuleSpec(_AZURE_NAMESPACE, None)
        ns_spec.submodule_search_locations = _submodule_dirs
        ns_pkg = importlib.util.module_from_spec(ns_spec)
        sys.modules[_AZURE_NAMESPACE] = ns_pkg


def uninstall():
    pass


def load_function(name: str, directory: str, script_file: str,
                  entry_point: typing.Optional[str]):
    dir_path = pathlib.Path(directory)
    script_path = pathlib.Path(script_file)
    if not entry_point:
        entry_point = 'main'

    register_function_dir(dir_path.parent)

    try:
        rel_script_path = script_path.relative_to(dir_path.parent)
    except ValueError:
        raise RuntimeError(
            f'script path {script_file} is not relative to the specified '
            f'directory {directory}'
        )

    last_part = rel_script_path.parts[-1]
    modname, ext = os.path.splitext(last_part)
    if ext != '.py':
        raise RuntimeError(
            f'cannot load function {name}: '
            f'invalid Python filename {script_file}')

    modname_parts = [_AZURE_NAMESPACE]
    modname_parts.extend(rel_script_path.parts[:-1])
    modname_parts.append(modname)

    fullmodname = '.'.join(modname_parts)

    mod = importlib.import_module(fullmodname)

    func = getattr(mod, entry_point, None)
    if func is None or not callable(func):
        raise RuntimeError(
            f'cannot load function {name}: function {entry_point}() is not '
            f'present in {rel_script_path}')

    return func
