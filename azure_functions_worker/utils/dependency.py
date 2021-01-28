from azure_functions_worker.utils.common import is_true_like
from typing import List, Optional
import importlib
import inspect
import os
import re
import sys

from ..logging import logger
from ..constants import (
    AZURE_WEBJOBS_SCRIPT_ROOT,
    PYTHON_ISOLATE_WORKER_DEPENDENCIES,
    PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT,
    PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_39
)
from ..utils.common import is_python_version
from ..utils.wrappers import enable_feature_by


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
        "/azure-functions-host/workers/python/3.6/LINUX/X64", # Worker's deps
        "/home/site/wwwroot" # CX's Working Directory
    ]

    Linux Dedicated/Premium sys.path: [
        "/home/site/wwwroot", # CX's Working Directory
        "/home/site/wwwroot/.python_packages/lib/site-packages", # CX's deps
        "/azure-functions-host/workers/python/3.6/LINUX/X64", # Worker's deps
    ]

    Core Tools sys.path: [
        "%appdata%\\azure-functions-core-tools\\bin\\workers\\"
            "python\\3.6\\WINDOWS\\X64", # Worker's deps
        "C:\\Users\\user\\Project\\.venv38\\lib\\site-packages", # CX's deps
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
    @enable_feature_by(
        flag=PYTHON_ISOLATE_WORKER_DEPENDENCIES,
        flag_default=(
            PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_39 if
            is_python_version('3.9') else
            PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT
        )
    )
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
        cls._remove_from_sys_path(cls.cx_deps_path)
        cls._remove_from_sys_path(cls.cx_working_dir)
        cls._add_to_sys_path(cls.worker_deps_path, True)
        logger.info(f'Start using worker dependencies {cls.worker_deps_path}')

    @classmethod
    @enable_feature_by(
        flag=PYTHON_ISOLATE_WORKER_DEPENDENCIES,
        flag_default=(
            PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_39 if
            is_python_version('3.9') else
            PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT
        )
    )
    def use_customer_dependencies(cls):
        """Switch the sys.path and ensure the customer's code import are loaded
        from CX's deppendencies.

        This will not affect already imported namespaces, but will clear out
        the module cache and ensure the upcoming modules are loaded from
        customer's dependency path.

        As for Linux Consumption, this will only remove worker_deps_path,
        but the customer's path will be loaded in function_environment_reload.

        The search order of a module name in customer frame is:
        1. cx_deps_path
        2. cx_working_dir
        """
        cls._remove_from_sys_path(cls.worker_deps_path)
        cls._add_to_sys_path(cls.cx_deps_path, True)
        cls._add_to_sys_path(cls.cx_working_dir, False)
        logger.info(f'Start using customer dependencies {cls.cx_deps_path}')

    @classmethod
    def reload_azure_google_namespace(cls, cx_working_dir: str):
        """Reload azure and google namespace, this including any modules in
        this namespace, such as azure-functions, grpcio, grpcio-tools etc.

        Depends on the PYTHON_ISOLATE_WORKER_DEPENDENCIES, the actual behavior
        differs.

        Parameters
        ----------
        cx_working_dir: str
            The path which contains customer's project file (e.g. wwwroot).
        """
        use_new_env = os.getenv(PYTHON_ISOLATE_WORKER_DEPENDENCIES)
        if use_new_env is None:
            use_new = (
                PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT_39 if
                is_python_version('3.9') else
                PYTHON_ISOLATE_WORKER_DEPENDENCIES_DEFAULT
            )
        else:
            use_new = is_true_like(use_new_env)

        if use_new:
            cls.reload_all_namespaces_from_customer_deps(cx_working_dir)
        else:
            cls.reload_azure_google_namespace_from_worker_deps()

    @classmethod
    def reload_azure_google_namespace_from_worker_deps(cls):
        """This is the old implementation of reloading azure and google
        namespace in Python worker directory. It is not actually re-importing
        the module but only reloads the module scripts from the worker path.

        It is not doing what it is intended, but due to it is already released
        on Linux Consumption production, we don't want to introduce regression
        on existing customers.

        Only intended to be used in Linux Consumption scenario.
        """
        # Reload package namespaces for customer's libraries
        packages_to_reload = ['azure', 'google']
        for p in packages_to_reload:
            try:
                logger.info(f'Reloading {p} module')
                importlib.reload(sys.modules[p])
            except Exception as ex:
                logger.info('Unable to reload {}: \n{}'.format(p, ex))
            logger.info(f'Reloaded {p} module')

        # Reload azure.functions to give user package precedence
        logger.info('Reloading azure.functions module at %s',
                    inspect.getfile(sys.modules['azure.functions']))
        try:
            importlib.reload(sys.modules['azure.functions'])
            logger.info('Reloaded azure.functions module now at %s',
                        inspect.getfile(sys.modules['azure.functions']))
        except Exception as ex:
            logger.info('Unable to reload azure.functions. '
                        'Using default. Exception:\n{}'.format(ex))

    @classmethod
    def reload_all_namespaces_from_customer_deps(cls, cx_working_dir: str):
        """This is a new implementation of reloading azure and google
        namespace from customer's .python_packages folder. Only intended to be
        used in Linux Consumption scenario.

        Parameters
        ----------
        cx_working_dir: str
            The path which contains customer's project file (e.g. wwwroot).
        """
        # Specialized working directory needs to be added
        working_directory: str = os.path.abspath(cx_working_dir)

        # Switch to customer deps and clear out all module cache in worker deps
        cls._remove_from_sys_path(cls.worker_deps_path)
        cls._add_to_sys_path(cls.cx_deps_path, True)
        cls._add_to_sys_path(working_directory, False)
        logger.info('Reloaded azure google namespaces from '
                    'customer dependencies')

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
            Core Tools: path to customer's site pacakges
            Linux Dedicated/Premium: path to customer's site pacakges
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
        # 1. Try to parse the absolute path python/3.8/LINUX/X64 in sys.path
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
        all_modules = set(sys.modules.keys()) - set(sys.builtin_module_names)
        for module_name in all_modules:
            module = sys.modules[module_name]
            # Module path can be actual file path or a pure namespace path
            # For actual files: use __file__ attribute to retrieve module path
            # For namespace: use __path__[0] to retrieve module path
            module_path = ''
            if getattr(module, '__file__', None):
                module_path = os.path.dirname(module.__file__)
            elif getattr(module, '__path__', None) and getattr(
                    module.__path__, '_path', None):
                module_path = module.__path__._path[0]

            if module_path.startswith(path):
                sys.modules.pop(module_name)
