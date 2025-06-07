"""Windows platform configuration for protobuf Buck2 integration.

This module provides Windows-specific configurations for protoc and plugins.
Implementation will be completed in Task 003.
"""

# Windows platform constants
WINDOWS_X86_64 = "windows-x86_64"

def get_windows_protoc_url(version: str, arch: str = "x86_64"):
    """Returns download URL for protoc on Windows."""
    # Placeholder implementation
    return f"https://github.com/protocolbuffers/protobuf/releases/download/v{version}/protoc-{version}-win64.zip"

def get_windows_plugin_url(plugin: str, version: str, arch: str = "x86_64"):
    """Returns download URL for protoc plugin on Windows."""
    # Placeholder implementation
    return f"https://github.com/{plugin}/releases/download/v{version}/{plugin}-windows-{arch}.exe"
