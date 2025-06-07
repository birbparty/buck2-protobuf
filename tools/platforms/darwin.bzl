"""macOS platform configuration for protobuf Buck2 integration.

This module provides macOS-specific configurations for protoc and plugins.
Implementation will be completed in Task 003.
"""

# macOS platform constants
DARWIN_X86_64 = "darwin-x86_64"
DARWIN_ARM64 = "darwin-aarch_64"

def get_darwin_protoc_url(version: str, arch: str = "x86_64"):
    """Returns download URL for protoc on macOS."""
    # Placeholder implementation
    return f"https://github.com/protocolbuffers/protobuf/releases/download/v{version}/protoc-{version}-osx-{arch}.zip"

def get_darwin_plugin_url(plugin: str, version: str, arch: str = "x86_64"):
    """Returns download URL for protoc plugin on macOS."""
    # Placeholder implementation
    return f"https://github.com/{plugin}/releases/download/v{version}/{plugin}-darwin-{arch}"
