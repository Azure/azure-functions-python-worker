# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import importlib
import importlib.machinery
import os
import os.path
import pathlib
import sys
from os import PathLike, fspath
from typing import Optional

from .utils.constants import (
    CUSTOMER_PACKAGES_PATH,
    MODULE_NOT_FOUND_TS_URL,
)
from .utils.wrappers import attach_message_to_exception

_AZURE_NAMESPACE = '__app__'
_DEFAULT_SCRIPT_FILENAME = '__init__.py'
_DEFAULT_ENTRY_POINT = 'main'
_submodule_dirs = []


def register_function_dir(path: PathLike) -> None:
    try:
        _submodule_dirs.append(fspath(path))
        # Update the namespace package's submodule search locations if it exists
        if _AZURE_NAMESPACE in sys.modules:
            sys.modules[
                _AZURE_NAMESPACE].__spec__.submodule_search_locations = _submodule_dirs
            # Also update __path__ which is required for namespace packages to work
            sys.modules[_AZURE_NAMESPACE].__path__ = _submodule_dirs
    except TypeError as e:
        raise RuntimeError('Path (%s) is incompatible with fspath. '
                           'It is of type %s.', path, type(path), e)


def install() -> None:
    if _AZURE_NAMESPACE not in sys.modules:
        # Create and register the __app__ namespace package.
        ns_spec = importlib.machinery.ModuleSpec(_AZURE_NAMESPACE, None)
        ns_spec.submodule_search_locations = _submodule_dirs
        ns_pkg = importlib.util.module_from_spec(ns_spec)
        # Set __path__ for namespace package
        ns_pkg.__path__ = _submodule_dirs
        sys.modules[_AZURE_NAMESPACE] = ns_pkg


@attach_message_to_exception(
    expt_type=(ImportError, ModuleNotFoundError),
    message="Cannot find module. Please check the requirements.txt"
            " file for the missing module."
            " For more info, please refer the troubleshooting guide: "
            + MODULE_NOT_FOUND_TS_URL
            + ". Current sys.path: " + " ".join(sys.path),
    debug_logs="Error in index_function_app. Sys Path:" + " ".join(sys.path)
               + ", python-packages Path exists: "
               + str(os.path.exists(CUSTOMER_PACKAGES_PATH)))
def load_function(name: str, directory: str, script_file: str,
                  entry_point: Optional[str]):
    dir_path = pathlib.Path(directory)
    script_path = pathlib.Path(script_file) if script_file else pathlib.Path(
        _DEFAULT_SCRIPT_FILENAME)
    if not entry_point:
        entry_point = _DEFAULT_ENTRY_POINT

    register_function_dir(dir_path.parent)

    try:
        rel_script_path = script_path.relative_to(dir_path.parent)
    except ValueError:
        raise RuntimeError(
            'script path %s is not relative to the specified '
            'directory %s', script_file, directory
        )

    last_part = rel_script_path.parts[-1]
    modname, ext = os.path.splitext(last_part)
    if ext != '.py':
        raise RuntimeError(
            'cannot load function %s: '
            'invalid Python filename %s', name, script_file)

    modname_parts = [_AZURE_NAMESPACE]
    modname_parts.extend(rel_script_path.parts[:-1])

    # If the __init__.py contains the code, we should avoid double loading.
    if modname.lower() != '__init__':
        modname_parts.append(modname)

    fullmodname = '.'.join(modname_parts)

    mod = importlib.import_module(fullmodname)

    func = getattr(mod, entry_point, None)
    if func is None or not callable(func):
        raise RuntimeError(
            'cannot load function %s: function %s() is not '
            'present in %s', name, entry_point, rel_script_path)

    return func
