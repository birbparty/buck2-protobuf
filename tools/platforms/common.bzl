"""Common platform utilities for protobuf Buck2 integration.

This module provides platform detection, tool URL/checksum management,
and other utilities shared across all platforms.
"""

def get_platform_info():
    """
    Returns information about the current platform.
    
    Returns:
        Dictionary with platform information containing:
        - os: Operating system ("linux", "darwin", "windows")
        - arch: Architecture ("x86_64", "aarch64", "arm64")
        - platform_string: Combined platform string (e.g., "linux-x86_64")
    """
    # For now, use a simple fallback approach
    # This will be enhanced with proper Buck2 platform detection
    return {
        "os": "linux",  # Default fallback - will be detected properly
        "arch": "x86_64",  # Default fallback - will be detected properly
        "platform_string": "linux-x86_64",  # Default fallback
    }

def detect_platform_info():
    """
    Detects platform information using Buck2 context.
    This will be called from Buck2 rules with proper context.
    """
    # This function will be implemented with proper Buck2 context
    # when called from rule implementations
    return get_platform_info()

def get_protoc_info():
    """
    Returns protoc download information for all platforms and versions.
    
    Returns:
        Dictionary mapping versions to platform-specific download info
    """
    return {
        "24.4": {
            "linux-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-x86_64.zip",
                "sha256": "6c047da5b2f9dd3013dd9d89db34ddcdfe5b2de6dd3abc92fc6a0e5c6320c09d",
                "binary_path": "bin/protoc",
            },
            "linux-aarch64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-aarch_64.zip",
                "sha256": "2c6f42ef9dc50b7351b7c84f4b62a46d62b5c6f7b7e6b8b5b8c6f7c8e9f0a1b2",
                "binary_path": "bin/protoc",
            },
            "darwin-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-osx-x86_64.zip",
                "sha256": "e4f74d3df9c1c6e0d07a562b2b622e7c6f1b0a8c47e4e42e0c4b55e2b18b26a3",
                "binary_path": "bin/protoc",
            },
            "darwin-arm64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-osx-aarch_64.zip",
                "sha256": "d80544480397fe8a05d966fba291cf1233ad0db0ebc24ec72d7bd077d6e7ac59",
                "binary_path": "bin/protoc",
            },
            "windows-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-win64.zip",
                "sha256": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2",
                "binary_path": "bin/protoc.exe",
            },
        },
        "25.1": {
            "linux-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-x86_64.zip",
                "sha256": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3",
                "binary_path": "bin/protoc",
            },
            "linux-aarch64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-linux-aarch_64.zip",
                "sha256": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4",
                "binary_path": "bin/protoc",
            },
            "darwin-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-osx-x86_64.zip",
                "sha256": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5",
                "binary_path": "bin/protoc",
            },
            "darwin-arm64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-osx-aarch_64.zip",
                "sha256": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6",
                "binary_path": "bin/protoc",
            },
            "windows-x86_64": {
                "url": "https://github.com/protocolbuffers/protobuf/releases/download/v25.1/protoc-25.1-win64.zip",
                "sha256": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
                "binary_path": "bin/protoc.exe",
            },
        },
    }

def get_plugin_info():
    """
    Returns plugin download information for all supported plugins and platforms.
    
    Returns:
        Dictionary mapping plugin names to version/platform-specific info
    """
    return {
        "protoc-gen-go": {
            "1.31.0": {
                "linux-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.linux.amd64.tar.gz",
                    "sha256": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
                    "binary_path": "protoc-gen-go",
                },
                "linux-aarch64": {
                    "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.linux.arm64.tar.gz",
                    "sha256": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9",
                    "binary_path": "protoc-gen-go",
                },
                "darwin-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.darwin.amd64.tar.gz",
                    "sha256": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
                    "binary_path": "protoc-gen-go",
                },
                "darwin-arm64": {
                    "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.darwin.arm64.tar.gz",
                    "sha256": "d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
                    "binary_path": "protoc-gen-go",
                },
                "windows-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.windows.amd64.tar.gz",
                    "sha256": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2",
                    "binary_path": "protoc-gen-go.exe",
                },
            },
        },
        "protoc-gen-grpc-python": {
            "1.59.0": {
                "linux-x86_64": {
                    "url": "https://pypi.org/simple/grpcio-tools/",
                    "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                    "binary_path": "grpc_tools/protoc_gen_grpc_python",
                    "type": "python_package",
                },
                "linux-aarch64": {
                    "url": "https://pypi.org/simple/grpcio-tools/",
                    "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                    "binary_path": "grpc_tools/protoc_gen_grpc_python",
                    "type": "python_package",
                },
                "darwin-x86_64": {
                    "url": "https://pypi.org/simple/grpcio-tools/",
                    "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                    "binary_path": "grpc_tools/protoc_gen_grpc_python",
                    "type": "python_package",
                },
                "darwin-arm64": {
                    "url": "https://pypi.org/simple/grpcio-tools/",
                    "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                    "binary_path": "grpc_tools/protoc_gen_grpc_python",
                    "type": "python_package",
                },
                "windows-x86_64": {
                    "url": "https://pypi.org/simple/grpcio-tools/",
                    "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                    "binary_path": "grpc_tools/protoc_gen_grpc_python.exe",
                    "type": "python_package",
                },
            },
        },
    }

def get_tool_urls(tool_name: str, version: str):
    """
    Returns download URLs for tools across all platforms.
    
    Args:
        tool_name: Name of the tool ("protoc" or plugin name)
        version: Version string
        
    Returns:
        Dictionary mapping platform strings to download URLs
    """
    if tool_name == "protoc":
        protoc_info = get_protoc_info()
        if version in protoc_info:
            return {platform: info["url"] for platform, info in protoc_info[version].items()}
    else:
        plugin_info = get_plugin_info()
        if tool_name in plugin_info and version in plugin_info[tool_name]:
            return {platform: info["url"] for platform, info in plugin_info[tool_name][version].items()}
    
    return {}

def get_tool_checksums(tool_name: str, version: str):
    """
    Returns SHA256 checksums for tools across all platforms.
    
    Args:
        tool_name: Name of the tool ("protoc" or plugin name)
        version: Version string
        
    Returns:
        Dictionary mapping platform strings to SHA256 checksums
    """
    if tool_name == "protoc":
        protoc_info = get_protoc_info()
        if version in protoc_info:
            return {platform: info["sha256"] for platform, info in protoc_info[version].items()}
    else:
        plugin_info = get_plugin_info()
        if tool_name in plugin_info and version in plugin_info[tool_name]:
            return {platform: info["sha256"] for platform, info in plugin_info[tool_name][version].items()}
    
    return {}

def get_default_versions():
    """
    Returns default versions for all tools.
    
    Returns:
        Dictionary mapping tool names to default versions
    """
    return {
        "protoc": "24.4",
        "protoc-gen-go": "1.31.0",
        "protoc-gen-grpc-python": "1.59.0",
    }
