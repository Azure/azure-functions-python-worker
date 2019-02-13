"""Python functions loader."""


import importlib
import importlib.machinery
import importlib.util
import os
import os.path
import pathlib
import sys
import typing

_submodule_dirs = []


def extract_func_app_namespace(func_dir):
    func_dir_path = pathlib.Path(func_dir)
    func_app_dir = os.path.normpath(func_dir_path.parent)
    func_app_namespace = os.path.basename(func_app_dir)
    return func_app_namespace


def register_function_dir(path: os.PathLike):
    _submodule_dirs.append(os.fspath(path))


def install_func_app_package(func_dir):
    func_app_namespace = extract_func_app_namespace(func_dir)
    if func_app_namespace not in sys.modules:
        # Create and register the function app namespace package.
        ns_spec = importlib.machinery.ModuleSpec(func_app_namespace, None)
        ns_spec.submodule_search_locations = _submodule_dirs
        ns_pkg = importlib.util.module_from_spec(ns_spec)
        sys.modules[func_app_namespace] = ns_pkg


def uninstall():
    pass


def load_function(name: str, directory: str, script_file: str,
                  entry_point: typing.Optional[str]):
    dir_path = pathlib.Path(directory)
    script_path = pathlib.Path(script_file)
    if not entry_point:
        entry_point = 'main'

    register_function_dir(dir_path.parent)
    
    func_app_namespace = extract_func_app_namespace(dir_path)

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
    
    modname_parts = [func_app_namespace]
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
