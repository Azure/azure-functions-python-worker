# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Execution utilities for FastAPI runtime.

Provides invocation ID tracking via ContextVar for async execution.
"""
import contextvars

# ContextVar for tracking invocation IDs across async contexts
# This is used by the proxy worker for logging and telemetry correlation
invocation_id_cv = contextvars.ContextVar('invocation_id', default=None)
