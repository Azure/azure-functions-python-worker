# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Logging configuration for FastAPI runtime"""
import logging

logger = logging.getLogger('azure_functions_fastapi_runtime')
logger.setLevel(logging.INFO)

# Add console handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
