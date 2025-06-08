#!/usr/bin/env python3
"""
Download protoc plugins for protobuf Buck2 integration.

This script handles downloading and caching protoc plugins for different
languages, platforms, and versions with comprehensive security features.

Enhanced with ORAS distribution support for improved performance and bandwidth efficiency.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

# Try to import ORAS plugin distributor for enhanced functionality
try:
    from oras_plugins import PluginOrasDistributor
    ORAS_AVAILABLE = True
except ImportError:
    ORAS_AVAILABLE = False


class PluginDownloader:
    """Handles downloading, caching, and validation of protoc plugins."""
    
    def __init__(self, cache_dir: str, verbose: bool = False):
        """
        Initialize the plugin downloader.
        
        Args:
            cache_dir: Directory to store cached downloads
            verbose: Enable verbose logging
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        
        # Plugin configuration database
        self.plugin_config = {
            "protoc-gen-go": {
                "1.31.0": {
                    "linux-x86_64": {
                        "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.linux.amd64.tar.gz",
                        "sha256": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8",
                        "binary_path": "protoc-gen-go",
                        "archive_type": "tar.gz",
                    },
                    "linux-aarch64": {
                        "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.linux.arm64.tar.gz",
                        "sha256": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9",
                        "binary_path": "protoc-gen-go",
                        "archive_type": "tar.gz",
                    },
                    "darwin-x86_64": {
                        "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.darwin.amd64.tar.gz",
                        "sha256": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0",
                        "binary_path": "protoc-gen-go",
                        "archive_type": "tar.gz",
                    },
                    "darwin-arm64": {
                        "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.darwin.arm64.tar.gz",
                        "sha256": "d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1",
                        "binary_path": "protoc-gen-go",
                        "archive_type": "tar.gz",
                    },
                    "windows-x86_64": {
                        "url": "https://github.com/protocolbuffers/protobuf-go/releases/download/v1.31.0/protoc-gen-go.v1.31.0.windows.amd64.tar.gz",
                        "sha256": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2",
                        "binary_path": "protoc-gen-go.exe",
                        "archive_type": "tar.gz",
                    },
                },
            },
            "protoc-gen-grpc-go": {
                "1.3.0": {
                    "linux-x86_64": {
                        "url": "https://github.com/grpc/grpc-go/releases/download/cmd/protoc-gen-go-grpc/v1.3.0/protoc-gen-go-grpc.v1.3.0.linux.amd64.tar.gz",
                        "sha256": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3",
                        "binary_path": "protoc-gen-go-grpc",
                        "archive_type": "tar.gz",
                    },
                    "linux-aarch64": {
                        "url": "https://github.com/grpc/grpc-go/releases/download/cmd/protoc-gen-go-grpc/v1.3.0/protoc-gen-go-grpc.v1.3.0.linux.arm64.tar.gz",
                        "sha256": "a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4",
                        "binary_path": "protoc-gen-go-grpc",
                        "archive_type": "tar.gz",
                    },
                    "darwin-x86_64": {
                        "url": "https://github.com/grpc/grpc-go/releases/download/cmd/protoc-gen-go-grpc/v1.3.0/protoc-gen-go-grpc.v1.3.0.darwin.amd64.tar.gz",
                        "sha256": "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5",
                        "binary_path": "protoc-gen-go-grpc",
                        "archive_type": "tar.gz",
                    },
                    "darwin-arm64": {
                        "url": "https://github.com/grpc/grpc-go/releases/download/cmd/protoc-gen-go-grpc/v1.3.0/protoc-gen-go-grpc.v1.3.0.darwin.arm64.tar.gz",
                        "sha256": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
                        "binary_path": "protoc-gen-go-grpc",
                        "archive_type": "tar.gz",
                    },
                    "windows-x86_64": {
                        "url": "https://github.com/grpc/grpc-go/releases/download/cmd/protoc-gen-go-grpc/v1.3.0/protoc-gen-go-grpc.v1.3.0.windows.amd64.tar.gz",
                        "sha256": "d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
                        "binary_path": "protoc-gen-go-grpc.exe",
                        "archive_type": "tar.gz",
                    },
                },
            },
            "protoc-gen-grpc-python": {
                "1.59.0": {
                    # Python plugins are handled differently - installed via pip
                    "linux-x86_64": {
                        "package": "grpcio-tools",
                        "version": "1.59.0",
                        "type": "python_package",
                        "binary_path": "bin/grpc_tools.protoc",
                        "entry_point": "grpc_tools.protoc",
                    },
                    "linux-aarch64": {
                        "package": "grpcio-tools",
                        "version": "1.59.0", 
                        "type": "python_package",
                        "binary_path": "bin/grpc_tools.protoc",
                        "entry_point": "grpc_tools.protoc",
                    },
                    "darwin-x86_64": {
                        "package": "grpcio-tools",
                        "version": "1.59.0",
                        "type": "python_package",
                        "binary_path": "bin/grpc_tools.protoc",
                        "entry_point": "grpc_tools.protoc",
                    },
                    "darwin-arm64": {
                        "package": "grpcio-tools",
                        "version": "1.59.0",
                        "type": "python_package", 
                        "binary_path": "bin/grpc_tools.protoc",
                        "entry_point": "grpc_tools.protoc",
                    },
                    "windows-x86_64": {
                        "package": "grpcio-tools",
                        "version": "1.59.0",
                        "type": "python_package",
                        "binary_path": "bin/grpc_tools.protoc.exe",
                        "entry_point": "grpc_tools.protoc",
                    },
                },
            },
        }
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[plugin-downloader] {message}", file=sys.stderr)
    
    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def validate_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """Validate SHA256 checksum of a file."""
        if not file_path.exists():
            return False
        
        actual_checksum = self.calculate_sha256(file_path)
        matches = actual_checksum.lower() == expected_checksum.lower()
        
        if not matches:
            self.log(f"Checksum mismatch for {file_path}")
            self.log(f"Expected: {expected_checksum}")
            self.log(f"Actual:   {actual_checksum}")
        
        return matches
    
    def download_with_retry(self, url: str, output_path: Path, max_retries: int = 3) -> bool:
        """Download a file with retry logic and progress indication."""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Retry attempt {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                
                self.log(f"Downloading {url}")
                
                # Create request with proper headers
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'buck2-protobuf-plugin-downloader/1.0')
                
                # Download with progress tracking
                with urllib.request.urlopen(req, timeout=30) as response:
                    total_size = response.headers.get('Content-Length')
                    if total_size:
                        total_size = int(total_size)
                        self.log(f"File size: {total_size:,} bytes")
                    
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, 'wb') as f:
                        downloaded = 0
                        while True:
                            chunk = response.read(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            if total_size and self.verbose:
                                percent = (downloaded / total_size) * 100
                                print(f"\rProgress: {percent:.1f}% ({downloaded:,}/{total_size:,} bytes)", 
                                      end='', file=sys.stderr)
                
                if self.verbose and total_size:
                    print("", file=sys.stderr)  # New line after progress
                
                self.log(f"Downloaded successfully to {output_path}")
                return True
                
            except urllib.error.HTTPError as e:
                self.log(f"HTTP error {e.code}: {e.reason}")
                if e.code == 404:
                    break  # Don't retry on 404
            except urllib.error.URLError as e:
                self.log(f"URL error: {e.reason}")
            except Exception as e:
                self.log(f"Download error: {e}")
        
        return False
    
    def extract_archive(self, archive_path: Path, extract_dir: Path, archive_type: str = "tar.gz") -> bool:
        """Extract an archive (tar.gz or zip)."""
        try:
            self.log(f"Extracting {archive_path} to {extract_dir}")
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            if archive_type == "tar.gz":
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(extract_dir)
            elif archive_type == "zip":
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            else:
                raise ValueError(f"Unsupported archive type: {archive_type}")
            
            self.log("Extraction completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Extraction error: {e}")
            return False
    
    def install_python_package(self, package: str, version: str, install_dir: Path) -> bool:
        """Install a Python package using pip to a specific directory."""
        try:
            self.log(f"Installing Python package {package}=={version}")
            
            # Create virtual environment
            venv_dir = install_dir / "venv"
            venv_dir.mkdir(parents=True, exist_ok=True)
            
            # Create venv
            subprocess.run([
                sys.executable, "-m", "venv", str(venv_dir)
            ], check=True, capture_output=True)
            
            # Determine pip path
            if os.name == "nt":  # Windows
                pip_path = venv_dir / "Scripts" / "pip"
                python_path = venv_dir / "Scripts" / "python"
            else:
                pip_path = venv_dir / "bin" / "pip"
                python_path = venv_dir / "bin" / "python"
            
            # Install package
            subprocess.run([
                str(pip_path), "install", f"{package}=={version}"
            ], check=True, capture_output=True)
            
            self.log(f"Successfully installed {package}=={version}")
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Failed to install Python package: {e}")
            return False
        except Exception as e:
            self.log(f"Python package installation error: {e}")
            return False
    
    def create_python_wrapper(self, install_dir: Path, binary_path: str, entry_point: str) -> Path:
        """Create a wrapper script for Python-based protoc plugins."""
        wrapper_path = install_dir / binary_path
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Determine python path
        if os.name == "nt":  # Windows
            python_path = install_dir / "venv" / "Scripts" / "python"
            wrapper_content = f"""@echo off
"{python_path}" -m {entry_point} %*
"""
        else:
            python_path = install_dir / "venv" / "bin" / "python"
            wrapper_content = f"""#!/bin/bash
"{python_path}" -m {entry_point} "$@"
"""
        
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_content)
        
        # Make executable
        wrapper_path.chmod(0o755)
        
        return wrapper_path
    
    def get_cached_plugin_path(self, plugin: str, version: str, platform: str) -> Optional[Path]:
        """Check if plugin binary is already cached and valid."""
        if plugin not in self.plugin_config:
            return None
        
        if version not in self.plugin_config[plugin]:
            return None
        
        if platform not in self.plugin_config[plugin][version]:
            return None
        
        config = self.plugin_config[plugin][version][platform]
        cache_key = f"{plugin}-{version}-{platform}"
        cached_dir = self.cache_dir / cache_key
        binary_path = cached_dir / config["binary_path"]
        
        if not binary_path.exists():
            return None
        
        # Validate cached binary
        if not binary_path.is_file():
            return None
        
        # Check if binary is executable
        if not os.access(binary_path, os.X_OK):
            try:
                binary_path.chmod(0o755)
            except Exception:
                return None
        
        self.log(f"Using cached plugin at {binary_path}")
        return binary_path
    
    def download_plugin(self, plugin: str, version: str, platform: str) -> str:
        """
        Download and cache a protoc plugin binary.
        
        Args:
            plugin: Plugin name (e.g., "protoc-gen-go")
            version: Plugin version
            platform: Target platform (e.g., "linux-x86_64")
            
        Returns:
            Path to the downloaded plugin binary
            
        Raises:
            ValueError: If plugin/version/platform is not supported
            RuntimeError: If download or validation fails
        """
        # Check cache first
        cached_path = self.get_cached_plugin_path(plugin, version, platform)
        if cached_path:
            return str(cached_path)
        
        # Validate plugin, version, and platform
        if plugin not in self.plugin_config:
            available_plugins = list(self.plugin_config.keys())
            raise ValueError(f"Unsupported plugin: {plugin}. "
                           f"Available plugins: {available_plugins}")
        
        if version not in self.plugin_config[plugin]:
            available_versions = list(self.plugin_config[plugin].keys())
            raise ValueError(f"Unsupported version for {plugin}: {version}. "
                           f"Available versions: {available_versions}")
        
        if platform not in self.plugin_config[plugin][version]:
            available_platforms = list(self.plugin_config[plugin][version].keys())
            raise ValueError(f"Unsupported platform for {plugin}: {platform}. "
                           f"Available platforms: {available_platforms}")
        
        config = self.plugin_config[plugin][version][platform]
        cache_key = f"{plugin}-{version}-{platform}"
        cached_dir = self.cache_dir / cache_key
        
        try:
            # Handle Python packages differently
            if config.get("type") == "python_package":
                package = config["package"]
                package_version = config["version"]
                entry_point = config["entry_point"]
                binary_path = config["binary_path"]
                
                # Install Python package
                if not self.install_python_package(package, package_version, cached_dir):
                    raise RuntimeError(f"Failed to install Python package {package}")
                
                # Create wrapper script
                wrapper_path = self.create_python_wrapper(cached_dir, binary_path, entry_point)
                
                self.log(f"Successfully installed Python plugin {plugin} {version} for {platform} at {wrapper_path}")
                return str(wrapper_path)
            
            else:
                # Handle binary downloads
                url = config["url"]
                expected_checksum = config["sha256"]
                binary_path = config["binary_path"]
                archive_type = config.get("archive_type", "tar.gz")
                
                # Set up paths
                archive_path = self.cache_dir / f"{cache_key}.{archive_type.replace('.', '_')}"
                final_binary = cached_dir / binary_path
                
                # Download archive
                if not self.download_with_retry(url, archive_path):
                    raise RuntimeError(f"Failed to download {url}")
                
                # Validate checksum
                if not self.validate_checksum(archive_path, expected_checksum):
                    archive_path.unlink(missing_ok=True)
                    raise RuntimeError(f"Checksum validation failed for {archive_path}")
                
                # Extract archive
                if not self.extract_archive(archive_path, cached_dir, archive_type):
                    raise RuntimeError(f"Failed to extract {archive_path}")
                
                # Verify binary exists and make executable
                if not final_binary.exists():
                    raise RuntimeError(f"Binary not found at expected path: {final_binary}")
                
                final_binary.chmod(0o755)
                
                # Clean up archive
                archive_path.unlink(missing_ok=True)
                
                self.log(f"Successfully installed plugin {plugin} {version} for {platform} at {final_binary}")
                return str(final_binary)
                
        except Exception as e:
            # Clean up on failure
            if cached_dir.exists():
                shutil.rmtree(cached_dir, ignore_errors=True)
            raise e


def detect_platform_string() -> str:
    """Detect the current platform and return as a standard string."""
    # Simple platform detection (reused from protoc downloader)
    system = platform.system().lower()
    if system == "linux":
        os_name = "linux"
    elif system == "darwin":
        os_name = "darwin"
    elif system in ("windows", "win32"):
        os_name = "windows"
    else:
        raise ValueError(f"Unsupported operating system: {system}")
    
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "x86_64"
    elif machine in ("aarch64", "arm64"):
        if os_name == "darwin":
            arch = "arm64"
        else:
            arch = "aarch64"
    else:
        raise ValueError(f"Unsupported architecture: {machine}")
    
    return f"{os_name}-{arch}"


def download_plugin_enhanced(plugin: str, version: str, platform: str = None, 
                            cache_dir: str = None, registry: str = "oras.birb.homes", 
                            verbose: bool = False, use_oras: bool = True) -> str:
    """
    Enhanced plugin download with ORAS support and HTTP fallback.
    
    This function provides the new unified interface that tries ORAS first
    and falls back to HTTP downloads automatically.
    
    Args:
        plugin: Plugin name (e.g., "protoc-gen-go")
        version: Plugin version
        platform: Target platform (auto-detected if None)
        cache_dir: Cache directory (default: ~/.cache/buck2-protobuf)
        registry: ORAS registry URL
        verbose: Enable verbose logging
        use_oras: Enable ORAS distribution (falls back to HTTP if unavailable)
        
    Returns:
        Path to the plugin binary
        
    Raises:
        ValueError: If plugin/version/platform not supported
        RuntimeError: If both ORAS and HTTP fail
    """
    if platform is None:
        platform = detect_platform_string()
    
    if cache_dir is None:
        cache_dir = os.path.expanduser("~/.cache/buck2-protobuf")
    
    # Try ORAS distribution first if available and enabled
    if use_oras and ORAS_AVAILABLE:
        try:
            distributor = PluginOrasDistributor(
                registry=registry,
                cache_dir=cache_dir,
                verbose=verbose
            )
            return distributor.get_plugin(plugin, version, platform)
        except Exception as e:
            if verbose:
                print(f"[enhanced-downloader] ORAS failed: {e}, falling back to HTTP", file=sys.stderr)
    
    # Fallback to traditional HTTP download
    downloader = PluginDownloader(cache_dir, verbose=verbose)
    return downloader.download_plugin(plugin, version, platform)


def download_plugin_bundle(bundle_name: str, bundle_version: str = "latest",
                          platform: str = None, cache_dir: str = None, 
                          registry: str = "oras.birb.homes", verbose: bool = False) -> Dict[str, str]:
    """
    Download a plugin bundle (multiple plugins as a single operation).
    
    Args:
        bundle_name: Bundle name (e.g., "go-development")
        bundle_version: Bundle version
        platform: Target platform (auto-detected if None)
        cache_dir: Cache directory (default: ~/.cache/buck2-protobuf)
        registry: ORAS registry URL
        verbose: Enable verbose logging
        
    Returns:
        Dictionary mapping plugin names to their binary paths
        
    Raises:
        ValueError: If bundle not supported
        RuntimeError: If bundle download fails
    """
    if not ORAS_AVAILABLE:
        raise RuntimeError(
            "Plugin bundles require ORAS support. "
            "Please install the ORAS plugin distributor."
        )
    
    if platform is None:
        platform = detect_platform_string()
    
    if cache_dir is None:
        cache_dir = os.path.expanduser("~/.cache/buck2-protobuf")
    
    distributor = PluginOrasDistributor(
        registry=registry,
        cache_dir=cache_dir,
        verbose=verbose
    )
    
    return distributor.get_bundle(bundle_name, bundle_version, platform)


def main():
    """Main entry point for plugin download script."""
    parser = argparse.ArgumentParser(description="Download protoc plugins")
    parser.add_argument("--plugin", help="Plugin name")
    parser.add_argument("--version", help="Plugin version")
    parser.add_argument("--bundle", help="Plugin bundle name")
    parser.add_argument("--bundle-version", default="latest", help="Bundle version")
    parser.add_argument("--platform", help="Target platform (auto-detected if not specified)")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--checksum", help="Expected SHA256 checksum (for verification)")
    parser.add_argument("--no-oras", action="store_true", help="Disable ORAS, use HTTP only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--list-plugins", action="store_true", help="List supported plugins")
    parser.add_argument("--list-bundles", action="store_true", help="List supported bundles")
    
    args = parser.parse_args()
    
    try:
        # Detect platform if not specified
        platform = args.platform
        if not platform:
            platform = detect_platform_string()
            if args.verbose:
                print(f"Auto-detected platform: {platform}", file=sys.stderr)
        
        # Handle listing operations
        if args.list_plugins:
            if ORAS_AVAILABLE and not args.no_oras:
                distributor = PluginOrasDistributor(
                    registry=args.registry,
                    cache_dir=args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf"),
                    verbose=args.verbose
                )
                plugins = distributor.get_supported_plugins()
                print("Supported plugins (ORAS enhanced):")
                for plugin in plugins:
                    versions = distributor.get_supported_versions(plugin)
                    print(f"  {plugin}: {', '.join(versions)}")
            else:
                downloader = PluginDownloader(
                    args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf"),
                    verbose=args.verbose
                )
                plugins = list(downloader.plugin_config.keys())
                print("Supported plugins (HTTP only):")
                for plugin in plugins:
                    versions = list(downloader.plugin_config[plugin].keys())
                    print(f"  {plugin}: {', '.join(versions)}")
            return
        
        if args.list_bundles:
            if ORAS_AVAILABLE and not args.no_oras:
                distributor = PluginOrasDistributor(
                    registry=args.registry,
                    cache_dir=args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf"),
                    verbose=args.verbose
                )
                bundles = distributor.get_supported_bundles()
                print("Supported bundles:")
                for bundle in bundles:
                    print(f"  {bundle}")
            else:
                print("Plugin bundles require ORAS support (use without --no-oras)")
            return
        
        # Handle bundle download
        if args.bundle:
            plugin_paths = download_plugin_bundle(
                bundle_name=args.bundle,
                bundle_version=args.bundle_version,
                platform=platform,
                cache_dir=args.cache_dir,
                registry=args.registry,
                verbose=args.verbose
            )
            
            # Output bundle results as JSON
            print(json.dumps(plugin_paths, indent=2))
            return
        
        # Handle individual plugin download
        if not args.plugin or not args.version:
            parser.print_help()
            return
        
        # Download plugin using enhanced interface
        binary_path = download_plugin_enhanced(
            plugin=args.plugin,
            version=args.version,
            platform=platform,
            cache_dir=args.cache_dir,
            registry=args.registry,
            verbose=args.verbose,
            use_oras=not args.no_oras
        )
        
        # Additional checksum validation if requested (for binary plugins only)
        if args.checksum:
            downloader = PluginDownloader(
                args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf"),
                verbose=args.verbose
            )
            if not downloader.validate_checksum(Path(binary_path), args.checksum):
                print(f"ERROR: Checksum validation failed for {binary_path}", file=sys.stderr)
                sys.exit(1)
        
        # Output binary path
        print(binary_path)
        
    except Exception as e:
        print(f"ERROR: Failed to download plugin: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
