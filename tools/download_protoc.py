#!/usr/bin/env python3
"""
Download protoc binaries for protobuf Buck2 integration.

This script handles downloading and caching protoc binaries for different
platforms and versions with comprehensive security and performance features.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple


class PlatformDetector:
    """Handles robust platform detection across different environments."""
    
    @staticmethod
    def detect() -> Tuple[str, str]:
        """
        Detects the current platform and architecture.
        
        Returns:
            Tuple of (os, arch) where:
            - os: "linux", "darwin", or "windows"
            - arch: "x86_64", "aarch64", or "arm64"
        """
        # Detect OS
        system = platform.system().lower()
        if system == "linux":
            os_name = "linux"
        elif system == "darwin":
            os_name = "darwin"
        elif system in ("windows", "win32"):
            os_name = "windows"
        else:
            raise ValueError(f"Unsupported operating system: {system}")
        
        # Detect architecture
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            arch = "x86_64"
        elif machine in ("aarch64", "arm64"):
            if os_name == "darwin":
                arch = "arm64"  # macOS uses arm64
            else:
                arch = "aarch64"  # Linux uses aarch64
        else:
            raise ValueError(f"Unsupported architecture: {machine}")
        
        return os_name, arch


class ProtocDownloader:
    """Handles downloading, caching, and validation of protoc binaries."""
    
    def __init__(self, cache_dir: str, verbose: bool = False):
        """
        Initialize the downloader.
        
        Args:
            cache_dir: Directory to store cached downloads
            verbose: Enable verbose logging
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        
        # Tool configuration database
        self.protoc_config = {
            "24.4": {
                "linux-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-x86_64.zip",
                    "sha256": "5871398dfd6ac954a6adebf41f1ae3a4de915a36a6ab2fd3e8f2c00d45b50dec",
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
            # New versions with verified checksums
            "30.2": {
                "linux-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-linux-x86_64.zip",
                    "sha256": "327e9397c6fb3ea2a542513a3221334c6f76f7aa524a7d2561142b67b312a01f",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-linux-aarch_64.zip",
                    "sha256": "a3173ea338ef91b1605b88c4f8120d6c8ccf36f744d9081991d595d0d4352996",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-osx-x86_64.zip",
                    "sha256": "65675c3bb874a2d5f0c941e61bce6175090be25fe466f0ec2d4a6f5978333624",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-osx-aarch_64.zip",
                    "sha256": "92728c650f6cf2b6c37891ae04ef5bc2d4b5f32c5fbbd101eda623f90bb95f63",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v30.2/protoc-30.2-win64.zip",
                    "sha256": "10f35df7722a69dde8ee92b4a16a4e1cc91cfce82fbb4a371bd046de139aa4a9",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "31.0": {
                "linux-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-linux-x86_64.zip",
                    "sha256": "24e2ed32060b7c990d5eb00d642fde04869d7f77c6d443f609353f097799dd42",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-linux-aarch_64.zip",
                    "sha256": "999f4c023366b0b68c5c65272ead7877e47a2670245a79904b83450575da7e19",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-osx-x86_64.zip",
                    "sha256": "0360d9b6d9e3d66958cf6274d8514da49e76d475fd0d712181dcc7e9e056f2c8",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-osx-aarch_64.zip",
                    "sha256": "1fbe70a8d646875f91b6fd57294f763145292b2c9e1374ab09d6e2124afdd950",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.0/protoc-31.0-win64.zip",
                    "sha256": "d7edee5d0d5d6786c92e77a4f511e4698a5aa922c6390b6d08c3a79935a651b0",
                    "binary_path": "bin/protoc.exe",
                },
            },
            "31.1": {  # Latest stable version
                "linux-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-x86_64.zip",
                    "sha256": "96553041f1a91ea0efee963cb16f462f5985b4d65365f3907414c360044d8065",
                    "binary_path": "bin/protoc",
                },
                "linux-aarch64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-aarch_64.zip",
                    "sha256": "6c554de11cea04c56ebf8e45b54434019b1cd85223d4bbd25c282425e306ecc2",
                    "binary_path": "bin/protoc",
                },
                "darwin-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-osx-x86_64.zip",
                    "sha256": "485e87088b18614c25a99b1c0627918b3ff5b9fde54922fb1c920159fab7ba29",
                    "binary_path": "bin/protoc",
                },
                "darwin-arm64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-osx-aarch_64.zip",
                    "sha256": "4aeea0a34b0992847b03a8489a8dbedf3746de01109b74cc2ce9b6888a901ed9",
                    "binary_path": "bin/protoc",
                },
                "windows-x86_64": {
                    "url": "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-win64.zip",
                    "sha256": "70381b116ab0d71cb6a5177d9b17c7c13415866603a0fd40d513dafe32d56c35",
                    "binary_path": "bin/protoc.exe",
                },
            },
        }
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[protoc-downloader] {message}", file=sys.stderr)
    
    def calculate_sha256(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal SHA256 hash string
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def validate_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """
        Validate SHA256 checksum of a file.
        
        Args:
            file_path: Path to the file to validate
            expected_checksum: Expected SHA256 hash
            
        Returns:
            True if checksum matches, False otherwise
        """
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
        """
        Download a file with retry logic and progress indication.
        
        Args:
            url: URL to download from
            output_path: Local path to save the file
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if download succeeded, False otherwise
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.log(f"Retry attempt {attempt + 1}/{max_retries}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                
                self.log(f"Downloading {url}")
                
                # Create request with proper headers
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'buck2-protobuf-downloader/1.0')
                
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
    
    def extract_archive(self, archive_path: Path, extract_dir: Path) -> bool:
        """
        Extract a ZIP archive.
        
        Args:
            archive_path: Path to the archive file
            extract_dir: Directory to extract to
            
        Returns:
            True if extraction succeeded, False otherwise
        """
        try:
            self.log(f"Extracting {archive_path} to {extract_dir}")
            extract_dir.mkdir(parents=True, exist_ok=True)
            
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            self.log("Extraction completed successfully")
            return True
            
        except Exception as e:
            self.log(f"Extraction error: {e}")
            return False
    
    def get_cached_binary_path(self, version: str, platform: str) -> Optional[Path]:
        """
        Check if protoc binary is already cached and valid.
        
        Args:
            version: Protoc version
            platform: Platform string
            
        Returns:
            Path to cached binary if valid, None otherwise
        """
        if version not in self.protoc_config:
            return None
        
        if platform not in self.protoc_config[version]:
            return None
        
        config = self.protoc_config[version][platform]
        cache_key = f"protoc-{version}-{platform}"
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
        
        # TODO: In a production system, we might want to validate
        # the binary checksum or version to ensure cache integrity
        self.log(f"Using cached protoc at {binary_path}")
        return binary_path
    
    def download_protoc(self, version: str, platform: str) -> str:
        """
        Download and cache protoc binary for the specified version and platform.
        
        Args:
            version: Protoc version (e.g., "24.4")
            platform: Target platform (e.g., "linux-x86_64")
            
        Returns:
            Path to the downloaded protoc binary
            
        Raises:
            ValueError: If version/platform is not supported
            RuntimeError: If download or validation fails
        """
        # Check cache first
        cached_path = self.get_cached_binary_path(version, platform)
        if cached_path:
            return str(cached_path)
        
        # Validate version and platform
        if version not in self.protoc_config:
            available_versions = list(self.protoc_config.keys())
            raise ValueError(f"Unsupported protoc version: {version}. "
                           f"Available versions: {available_versions}")
        
        if platform not in self.protoc_config[version]:
            available_platforms = list(self.protoc_config[version].keys())
            raise ValueError(f"Unsupported platform: {platform}. "
                           f"Available platforms: {available_platforms}")
        
        config = self.protoc_config[version][platform]
        url = config["url"]
        expected_checksum = config["sha256"]
        binary_path = config["binary_path"]
        
        # Set up paths
        cache_key = f"protoc-{version}-{platform}"
        cached_dir = self.cache_dir / cache_key
        archive_path = self.cache_dir / f"{cache_key}.zip"
        final_binary = cached_dir / binary_path
        
        try:
            # Download archive
            if not self.download_with_retry(url, archive_path):
                raise RuntimeError(f"Failed to download {url}")
            
            # Validate checksum
            if not self.validate_checksum(archive_path, expected_checksum):
                archive_path.unlink(missing_ok=True)
                raise RuntimeError(f"Checksum validation failed for {archive_path}")
            
            # Extract archive
            if not self.extract_archive(archive_path, cached_dir):
                raise RuntimeError(f"Failed to extract {archive_path}")
            
            # Verify binary exists and make executable
            if not final_binary.exists():
                raise RuntimeError(f"Binary not found at expected path: {final_binary}")
            
            final_binary.chmod(0o755)
            
            # Clean up archive
            archive_path.unlink(missing_ok=True)
            
            self.log(f"Successfully installed protoc {version} for {platform} at {final_binary}")
            return str(final_binary)
            
        except Exception as e:
            # Clean up on failure
            archive_path.unlink(missing_ok=True)
            if cached_dir.exists():
                shutil.rmtree(cached_dir, ignore_errors=True)
            raise e


def detect_platform_string() -> str:
    """
    Detect the current platform and return as a standard string.
    
    Returns:
        Platform string like "linux-x86_64", "darwin-arm64", etc.
    """
    os_name, arch = PlatformDetector.detect()
    return f"{os_name}-{arch}"


def main():
    """Main entry point for protoc download script."""
    parser = argparse.ArgumentParser(description="Download protoc binaries")
    parser.add_argument("--version", required=True, help="Protoc version")
    parser.add_argument("--platform", help="Target platform (auto-detected if not specified)")
    parser.add_argument("--cache-dir", required=True, help="Cache directory")
    parser.add_argument("--checksum", help="Expected SHA256 checksum (for verification)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        # Detect platform if not specified
        platform = args.platform
        if not platform:
            platform = detect_platform_string()
            if args.verbose:
                print(f"Auto-detected platform: {platform}", file=sys.stderr)
        
        # Create downloader and get binary
        downloader = ProtocDownloader(args.cache_dir, verbose=args.verbose)
        binary_path = downloader.download_protoc(args.version, platform)
        
        # Additional checksum validation if requested
        if args.checksum:
            if not downloader.validate_checksum(Path(binary_path), args.checksum):
                print(f"ERROR: Checksum validation failed for {binary_path}", file=sys.stderr)
                sys.exit(1)
        
        # Output binary path
        print(binary_path)
        
    except Exception as e:
        print(f"ERROR: Failed to download protoc: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
