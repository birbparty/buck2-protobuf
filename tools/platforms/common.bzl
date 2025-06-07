"""Common platform utilities for protobuf Buck2 integration.

This module provides common functionality shared across all platforms.
Implementation will be completed in Task 003.
"""

def get_platform_info():
    """
    Returns information about the current platform.
    
    Will be fully implemented in Task 003.
    
    Returns:
        Dictionary with platform information
    """
    # Placeholder implementation
    return {
        "os": "unknown",
        "arch": "unknown",
        "platform_string": "unknown-unknown",
    }

def get_tool_urls(tool_name: str, version: str):
    """
    Returns download URLs for tools across all platforms.
    
    Will be fully implemented in Task 003.
    """
    # Placeholder implementation
    return {}

def get_tool_checksums(tool_name: str, version: str):
    """
    Returns SHA256 checksums for tools across all platforms.
    
    Will be fully implemented in Task 003.
    """
    # Placeholder implementation
    return {}
