# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Runtime Base Classes and Metaclass Registration

This module provides the core abstractions for runtime packages:
- RuntimeTrackerMeta: Metaclass that auto-registers runtimes at import time
- RuntimeBase: Abstract base class that all runtimes must extend
- RuntimeFeatureChecker: Utility to check if a runtime is loaded
"""

import abc
from abc import abstractmethod

base_runtime_module = __name__


class RuntimeTrackerMeta(type):
    """
    Metaclass that automatically registers runtime implementations.
    
    When a runtime class is defined with this metaclass, it automatically
    registers its module name. This allows the proxy worker to discover
    which runtime is loaded without explicit registration.
    
    Similar to ModuleTrackerMeta in azurefunctions.extensions.base
    """
    _module = None
    _runtime_name = None
    
    def __new__(cls, name, bases, dct, **kwargs):
        new_class = super().__new__(cls, name, bases, dct)
        new_module = dct.get("__module__")
        runtime_name = dct.get("runtime_name")
        
        # Only register if this is not the base module itself
        if new_module != base_runtime_module:
            if cls._module is None:
                cls._module = new_module
                cls._runtime_name = runtime_name
            elif cls._module != new_module:
                raise Exception(
                    f"Only one runtime package shall be imported at a time. "
                    f"{cls._module} and {new_module} are imported."
                )
        
        return new_class
    
    @classmethod
    def get_module(cls):
        """Get the registered runtime module name"""
        return cls._module
    
    @classmethod
    def get_runtime_name(cls):
        """Get the registered runtime name"""
        return cls._runtime_name
    
    @classmethod
    def module_imported(cls):
        """Check if a runtime module has been imported"""
        return cls._module is not None


class RuntimeBase(metaclass=RuntimeTrackerMeta):
    """
    Abstract base class for all runtime implementations.
    
    Runtime packages (FastAPI, Flask, etc.) must:
    1. Import this base class
    2. Create a subclass with runtime_name defined
    3. Implement all required event handler methods
    
    Example:
        from runtimes.base import RuntimeBase
        
        class Runtime(RuntimeBase):
            runtime_name = "fastapi"
            
            async def worker_init_request(self, request):
                # Implementation
                pass
    """
    
    # Runtime identification (must be set by subclass)
    runtime_name = None
    
    @abstractmethod
    async def worker_init_request(self, request):
        """
        Handle WorkerInitRequest - Initialize the runtime
        
        Args:
            request: WorkerInitRequest protobuf message
            
        Returns:
            WorkerInitResponse protobuf message
        """
        raise NotImplementedError()
    
    @abstractmethod
    async def functions_metadata_request(self, request):
        """
        Handle FunctionMetadataRequest - Return function metadata
        
        Args:
            request: FunctionMetadataRequest protobuf message
            
        Returns:
            FunctionMetadataResponse protobuf message
        """
        raise NotImplementedError()
    
    @abstractmethod
    async def function_load_request(self, request):
        """
        Handle FunctionLoadRequest - Load a specific function
        
        Args:
            request: FunctionLoadRequest protobuf message
            
        Returns:
            FunctionLoadResponse protobuf message
        """
        raise NotImplementedError()
    
    @abstractmethod
    async def invocation_request(self, request):
        """
        Handle InvocationRequest - Execute a function invocation
        
        Args:
            request: InvocationRequest protobuf message
            
        Returns:
            InvocationResponse protobuf message
        """
        raise NotImplementedError()
    
    @abstractmethod
    async def function_environment_reload_request(self, request):
        """
        Handle FunctionEnvironmentReloadRequest - Reload the environment
        
        Args:
            request: FunctionEnvironmentReloadRequest protobuf message
            
        Returns:
            FunctionEnvironmentReloadResponse protobuf message
        """
        raise NotImplementedError()


class RuntimeFeatureChecker:
    """
    Utility class to check if a runtime has been loaded.
    
    Similar to HttpV2FeatureChecker in azurefunctions.extensions.base
    """
    
    @staticmethod
    def runtime_loaded():
        """Check if a runtime has been imported and registered"""
        return RuntimeTrackerMeta.module_imported()
    
    @staticmethod
    def get_runtime_name():
        """Get the name of the loaded runtime"""
        return RuntimeTrackerMeta.get_runtime_name()
