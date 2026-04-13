# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Runtime Base Package for Azure Functions Python Worker

This package provides the base abstractions and metaclass-based registration
system for runtime packages. Runtime implementations (FastAPI, Flask, etc.)
extend these base classes, and the metaclass automatically registers them
at import time.

Pattern inspired by azurefunctions.extensions.base
"""

from .runtime import (
    RuntimeTrackerMeta,
    RuntimeBase,
    RuntimeFeatureChecker,
)

__all__ = [
    "RuntimeTrackerMeta",
    "RuntimeBase", 
    "RuntimeFeatureChecker",
]

__version__ = "0.1.0"
