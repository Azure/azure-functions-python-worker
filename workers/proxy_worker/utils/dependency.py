# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
import os
import re
import sys
from types import ModuleType
from typing import List, Optional

from ..logging import logger
from .common import is_envvar_true
from .constants import AZURE_WEBJOBS_SCRIPT_ROOT, CONTAINER_NAME


class DependencyManager:
    """The dependency manager controls the Python packages source, preventing
    worker packages interfer customer's code.

    It has two mode, in worker mode, the Python packages are loaded from worker
    path, (e.g. workers/python/<python_version>/<os>/<arch>). In customer mode,
    the packages are loaded from customer's .python_packages/ folder or from
    their virtual environment.

    Azure Functions has three different set of sys.path ordering,

    Linux Consumption sys.path: [
        "/tmp/functions\\standby\\wwwroot", # Placeholder folder
        "/home/site/wwwroot/.python_packages/lib/site-packages", # CX's deps
        "/azure-functions-host/workers/python/3.13/LINUX/X64", # Worker's deps
        "/home/site/wwwroot" # CX's Working Directory
    ]

    Linux Dedicated/Premium sys.path: [
        "/home/site/wwwroot", # CX's Working Directory
        "/home/site/wwwroot/.python_packages/lib/site-packages", # CX's deps
        "/azure-functions-host/workers/python/3.13/LINUX/X64", # Worker's deps
    ]

    Core Tools sys.path: [
        "%appdata%\\azure-functions-core-tools\\bin\\workers\\"
            "python\\3.13\\WINDOWS\\X64", # Worker's deps
        "C:\\Users\\user\\Project\\.venv311\\lib\\site-packages", # CX's deps
        "C:\\Users\\user\\Project", # CX's Working Directory
    ]

    When we first start up the Python worker, we should only loaded from
    worker's deps and create module namespace (e.g. google.protobuf variable).

    Once the worker receives worker init request, we clear out the sys.path,
    worker sys.modules cache and sys.path_import_cache so the libraries
    will only get loaded from CX's deps path.
    """

    cx_deps_path: str = ''
    cx_working_dir: str = ''
    worker_deps_path: str = ''

    @classmethod
    def initialize(cls):
        cls.cx_deps_path = cls._get_cx_deps_path()
        cls.cx_working_dir = cls._get_cx_working_dir()
        cls.worker_deps_path = cls._get_worker_deps_path()

    @classmethod
    def is_in_linux_consumption(cls):
        return CONTAINER_NAME in os.environ

    @classmethod
    def should_load_cx_dependencies(cls):
        """
         Customer dependencies should be loaded when
         1) App is a dedicated app
         2) App is linux consumption but not in placeholder mode.
         This can happen when the worker restarts for any reason
         (OOM, timeouts etc) and env reload request is not called.
        """
        return not (DependencyManager.is_in_linux_consumption()
                    and is_envvar_true("WEBSITE_PLACEHOLDER_MODE"))

    @classmethod
    def use_worker_dependencies(cls):
        """Switch the sys.path and ensure the worker imports are loaded from
        Worker's dependenciess.

        This will not affect already imported namespaces, but will clear out
        the module cache and ensure the upcoming modules are loaded from
        worker's dependency path.
        """

        # The following log line will not show up in core tools but should
        # work in kusto since core tools only collects gRPC logs. This function
        # is executed even before the gRPC logging channel is ready.
        logger.info('Applying use_worker_dependencies:'
                    ' worker_dependencies: %s,'
                    ' customer_dependencies: %s,'
                    ' working_directory: %s', cls.worker_deps_path,
                    cls.cx_deps_path, cls.cx_working_dir)

        cls._remove_from_sys_path(cls.cx_deps_path)
        cls._remove_from_sys_path(cls.cx_working_dir)
        cls._add_to_sys_path(cls.worker_deps_path, True)
        logger.info('Start using worker dependencies %s. Sys.path: %s',
                    cls.worker_deps_path, sys.path)

    @classmethod
    def prioritize_customer_dependencies(cls, cx_working_dir=None):
        """Switch the sys.path and ensure the customer's code import are loaded
        from CX's deppendencies.

        This will not affect already imported namespaces, but will clear out
        the module cache and ensure the upcoming modules are loaded from
        customer's dependency path.

        As for Linux Consumption, this will only remove worker_deps_path,
        but the customer's path will be loaded in function_environment_reload.

        The search order of a module name in customer's paths is:
        1. cx_deps_path
        2. worker_deps_path
        3. cx_working_dir
        """
        # Try to get the latest customer's working directory
        # cx_working_dir => cls.cx_working_dir => AzureWebJobsScriptRoot
        working_directory: str = ''
        if cx_working_dir:
            working_directory = os.path.abspath(cx_working_dir)
        if not working_directory:
            working_directory = cls.cx_working_dir
        if not working_directory:
            working_directory = os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT, '')

        # Try to get the latest customer's dependency path
        cx_deps_path: str = cls._get_cx_deps_path()

        if not cx_deps_path:
            cx_deps_path = cls.cx_deps_path

        logger.info(
            'Applying prioritize_customer_dependencies: '
            'worker_dependencies_path: %s, customer_dependencies_path: %s, '
            'working_directory: %s, Linux Consumption: %s, Placeholder: %s, '
            'sys.path: %s',
            cls.worker_deps_path, cx_deps_path, working_directory,
            DependencyManager.is_in_linux_consumption(),
            is_envvar_true("WEBSITE_PLACEHOLDER_MODE"), sys.path)

        cls._remove_from_sys_path(cls.worker_deps_path)
        cls._add_to_sys_path(cls.worker_deps_path, True)
        cls._add_to_sys_path(cls.cx_deps_path, True)
        cls._add_to_sys_path(working_directory, False)

        logger.info(f'Finished prioritize_customer_dependencies: {sys.path}')

    @classmethod
    def _add_to_sys_path(cls, path: str, add_to_first: bool):
        """This will ensure no duplicated path are added into sys.path and
        clear importer cache. No action if path already exists in sys.path.

        Parameters
        ----------
        path: str
            The path needs to be added into sys.path.
            If the path is an empty string, no action will be taken.
        add_to_first: bool
            Should the path added to the first entry (highest priority)
        """
        if path and path not in sys.path:
            if add_to_first:
                sys.path.insert(0, path)
            else:
                sys.path.append(path)

            # Only clear path importer and sys.modules cache if path is not
            # defined in sys.path
            cls._clear_path_importer_cache_and_modules(path)

    @classmethod
    def _remove_from_sys_path(cls, path: str):
        """This will remove path from sys.path and clear importer cache.
        No action if the path does not exist in sys.path.

        Parameters
        ----------
        path: str
            The path to be removed from sys.path.
            If the path is an empty string, no action will be taken.
        """
        if path and path in sys.path:
            # Remove all occurances in sys.path
            sys.path = list(filter(lambda p: p != path, sys.path))

        # In case if any part of worker initialization do sys.path.pop()
        # Always do a cache clear in path importer and sys.modules
        cls._clear_path_importer_cache_and_modules(path)

    @classmethod
    def _clear_path_importer_cache_and_modules(cls, path: str):
        """Removes path from sys.path_importer_cache and clear related
        sys.modules cache. No action if the path is empty or no entries
        in sys.path_importer_cache or sys.modules.

        Parameters
        ----------
        path: str
            The path to be removed from sys.path_importer_cache. All related
            modules will be cleared out from sys.modules cache.
            If the path is an empty string, no action will be taken.
        """
        if path and path in sys.path_importer_cache:
            sys.path_importer_cache.pop(path)

        if path:
            cls._remove_module_cache(path)

    @staticmethod
    def _get_cx_deps_path() -> str:
        """Get the directory storing the customer's third-party libraries.

        Returns
        -------
        str
            Core Tools: path to customer's site packages
            Linux Dedicated/Premium: path to customer's site packages
            Linux Consumption: empty string
        """
        prefix: Optional[str] = os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT)
        cx_paths: List[str] = [
            p for p in sys.path
            if prefix and p.startswith(prefix) and ('site-packages' in p)
        ]
        # Return first or default of customer path
        return (cx_paths or [''])[0]

    @staticmethod
    def _get_cx_working_dir() -> str:
        """Get the customer's working directory.

        Returns
        -------
        str
            Core Tools: AzureWebJobsScriptRoot env variable
            Linux Dedicated/Premium: AzureWebJobsScriptRoot env variable
            Linux Consumption: empty string
        """
        return os.getenv(AZURE_WEBJOBS_SCRIPT_ROOT, '')

    @staticmethod
    def _get_worker_deps_path() -> str:
        """Get the worker dependency sys.path. This will always available
        even in all skus.

        Returns
        -------
        str
            The worker packages path
        """
        # 1. Try to parse the absolute path python/3.13/LINUX/X64 in sys.path
        r = re.compile(r'.*python(\/|\\)\d+\.\d+(\/|\\)(WINDOWS|LINUX|OSX).*')
        worker_deps_paths: List[str] = [p for p in sys.path if r.match(p)]
        if worker_deps_paths:
            return worker_deps_paths[0]

        # 2. If it fails to find one, try to find one from the parent path
        #    This is used for handling the CI/localdev environment
        return os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..')
        )

    @staticmethod
    def _remove_module_cache(path: str):
        """Remove module cache if the module is imported from specific path.
        This will not impact builtin modules

        Parameters
        ----------
        path: str
            The module cache to be removed if it is imported from this path.
        """
        if not path:
            return

        not_builtin = set(sys.modules.keys()) - set(sys.builtin_module_names)

        # Don't reload proxy_worker
        to_be_cleared_from_cache = set([
            module_name for module_name in not_builtin
            if not module_name.startswith('proxy_worker')
        ])

        for module_name in to_be_cleared_from_cache:
            module = sys.modules.get(module_name)
            if not isinstance(module, ModuleType):
                continue

            # Module path can be actual file path or a pure namespace path.
            # Both of these has the module path placed in __path__ property
            # The property .__path__ can be None or does not exist in module
            try:
                # Safely check for __path__ and __file__ existence
                module_paths = set()
                if hasattr(module, '__path__') and module.__path__:
                    module_paths.update(module.__path__)
                if hasattr(module, '__file__') and module.__file__:
                    module_paths.add(module.__file__)

                if any([p for p in module_paths if p.startswith(path)]):
                    sys.modules.pop(module_name)
            except Exception as e:
                logger.warning(
                    'Attempt to remove module cache for %s but failed with '
                    '%s. Using the original module cache.',
                    module_name, e)
