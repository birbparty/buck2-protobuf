"""Linux platform configuration for protobuf Buck2 integration.

This module provides Linux-specific configurations for protoc and plugins.
Implementation will be completed in Task 003.
"""

# Linux platform constants
LINUX_X86_64 = "linux-x86_64"
LINUX_AARCH64 = "linux-aarch64"

def get_linux_protoc_url(version: str, arch: str = "x86_64"):
    """Returns download URL for protoc on Linux."""
    # Placeholder implementation
    return f"https://github.com/protocolbuffers/protobuf/releases/download/v{version}/protoc-{version}-linux-{arch}.zip"

def get_linux_plugin_url(plugin: str, version: str, arch: str = "x86_64"):
    """Returns download URL for protoc plugin on Linux."""
    # Placeholder implementation
    return f"https://github.com/{plugin}/releases/download/v{version}/{plugin}-linux-{arch}"
