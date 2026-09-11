# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""App setting manager for FastAPI runtime"""
import os
from typing import Optional


def get_app_setting(setting: str, default_value: Optional[str] = None) -> str:
    """
    Get an application setting from environment variables
    
    Args:
        setting: The name of the setting to retrieve
        default_value: Default value if setting is not found
        
    Returns:
        The setting value or default_value
    """
    return os.environ.get(setting, default_value)
