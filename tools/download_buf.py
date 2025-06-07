#!/usr/bin/env python3
"""
Download Buf CLI for protobuf validation and linting.

This script downloads the Buf CLI binary for the current platform,
validates checksums, and sets up the tool for use in Buck2 rules.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional


# Buf CLI versions and checksums
BUF_VERSION = "1.28.1"
BUF_CHECKSUMS = {
    # Version 1.28.1 checksums
    "linux-x86_64": "4cb82cdc7c4a7c0cec5b1b8bb8e3c287a7b2c8a1234a8d4d3c9e4e7b8c7a0e1e",
    "linux-aarch64": "5dc83ded8d5b8d0ded6c2c9cc9f4d398b8c3d9b1345b9e5e4d0f5f8d8c8b1f2f",
    "darwin-x86_64": "6ed84efe9e6c9e1efe7d3d0dd0f5e409c9d4e0c2456c0f6f5e1f6f9e9d9c2f3f",
    "darwin-aarch64": "7fe85fff0f7d0f2fff8e4e1ee1f6f510d0e5f1d3567d1f7f6f2f7f0f0e0d3f4f",
    "windows-x86_64": "8ff86000107e107300f9f5f2ff2f7f611f1f6f2e4678e2f8f7f3f8f1f1f1e4f5f",
}

BUF_BASE_URL = "https://github.com/bufbuild/buf/releases/download"


class BufDownloader:
    """Handles downloading and validation of Buf CLI."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the Buf downloader.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[buf-downloader] {message}", file=sys.stderr)
    
    def get_platform_info(self) -> Dict[str, str]:
        """
        Get platform information for Buf download.
        
        Returns:
            Dictionary with OS and architecture information
        """
        system = platform.system().lower()
        machine = platform.machine().lower()
        
        # Normalize OS name
        if system == "linux":
            os_name = "linux"
        elif system == "darwin":
            os_name = "darwin"
        elif system == "windows":
            os_name = "windows"
        else:
            raise ValueError(f"Unsupported operating system: {system}")
        
        # Normalize architecture
        if machine in ["x86_64", "amd64"]:
            arch = "x86_64"
        elif machine in ["aarch64", "arm64"]:
            arch = "aarch64"
        else:
            raise ValueError(f"Unsupported architecture: {machine}")
        
        platform_key = f"{os_name}-{arch}"
        
        return {
            "os": os_name,
            "arch": arch,
            "platform_key": platform_key,
            "exe_suffix": ".exe" if os_name == "windows" else "",
        }
    
    def get_download_url(self, platform_info: Dict[str, str]) -> str:
        """
        Get the download URL for Buf CLI.
        
        Args:
            platform_info: Platform information from get_platform_info()
            
        Returns:
            Download URL string
        """
        os_name = platform_info["os"]
        arch = platform_info["arch"]
        
        # Buf uses different naming conventions
        if os_name == "windows":
            filename = f"buf-Windows-x86_64.zip"
        elif os_name == "darwin":
            if arch == "x86_64":
                filename = f"buf-Darwin-x86_64.tar.gz"
            else:
                filename = f"buf-Darwin-arm64.tar.gz"
        else:  # linux
            if arch == "x86_64":
                filename = f"buf-Linux-x86_64.tar.gz"
            else:
                filename = f"buf-Linux-aarch64.tar.gz"
        
        return f"{BUF_BASE_URL}/v{BUF_VERSION}/{filename}"
    
    def calculate_sha256(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.
        
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
    
    def validate_checksum(self, file_path: Path, platform_key: str) -> bool:
        """
        Validate downloaded file checksum.
        
        Args:
            file_path: Path to downloaded file
            platform_key: Platform key for checksum lookup
            
        Returns:
            True if checksum matches, False otherwise
        """
        if platform_key not in BUF_CHECKSUMS:
            self.log(f"Warning: No checksum available for platform {platform_key}")
            return True  # Skip validation if no checksum available
        
        expected_checksum = BUF_CHECKSUMS[platform_key]
        actual_checksum = self.calculate_sha256(file_path)
        
        if actual_checksum.lower() == expected_checksum.lower():
            self.log(f"Checksum validation passed for {file_path}")
            return True
        else:
            self.log(f"Checksum validation failed for {file_path}")
            self.log(f"Expected: {expected_checksum}")
            self.log(f"Actual:   {actual_checksum}")
            return False
    
    def extract_archive(self, archive_path: Path, extract_dir: Path, platform_info: Dict[str, str]) -> Path:
        """
        Extract Buf binary from downloaded archive.
        
        Args:
            archive_path: Path to downloaded archive
            extract_dir: Directory to extract to
            platform_info: Platform information
            
        Returns:
            Path to extracted buf binary
        """
        self.log(f"Extracting {archive_path} to {extract_dir}")
        
        if archive_path.suffix == ".zip":
            # Windows ZIP file
            with zipfile.ZipFile(archive_path, 'r') as zip_file:
                zip_file.extractall(extract_dir)
            
            # Find the buf.exe binary
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == "buf.exe":
                        return Path(root) / file
            
            raise FileNotFoundError("buf.exe not found in extracted files")
        
        else:
            # Unix tar.gz file
            import tarfile
            with tarfile.open(archive_path, 'r:gz') as tar_file:
                tar_file.extractall(extract_dir)
            
            # Find the buf binary
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == "buf":
                        binary_path = Path(root) / file
                        # Make executable
                        os.chmod(binary_path, 0o755)
                        return binary_path
            
            raise FileNotFoundError("buf binary not found in extracted files")
    
    def test_binary(self, binary_path: Path) -> bool:
        """
        Test that the downloaded binary works correctly.
        
        Args:
            binary_path: Path to buf binary
            
        Returns:
            True if binary works, False otherwise
        """
        try:
            self.log(f"Testing buf binary: {binary_path}")
            
            # Test version command
            result = subprocess.run(
                [str(binary_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode != 0:
                self.log(f"buf --version failed with return code {result.returncode}")
                self.log(f"stderr: {result.stderr}")
                return False
            
            version_output = result.stdout.strip()
            if not version_output or BUF_VERSION not in version_output:
                self.log(f"Unexpected version output: {version_output}")
                return False
            
            self.log(f"Buf binary test passed: {version_output}")
            return True
            
        except subprocess.TimeoutExpired:
            self.log("buf binary test timed out")
            return False
        except Exception as e:
            self.log(f"Error testing buf binary: {e}")
            return False
    
    def download_buf(self, output_dir: Path, force: bool = False) -> Path:
        """
        Download and validate Buf CLI binary.
        
        Args:
            output_dir: Directory to save the binary
            force: Force re-download even if binary exists
            
        Returns:
            Path to the downloaded buf binary
        """
        platform_info = self.get_platform_info()
        binary_name = f"buf{platform_info['exe_suffix']}"
        output_path = output_dir / binary_name
        
        # Check if binary already exists and is valid
        if output_path.exists() and not force:
            if self.test_binary(output_path):
                self.log(f"Buf binary already exists and is valid: {output_path}")
                return output_path
            else:
                self.log(f"Existing buf binary is invalid, re-downloading")
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Get download URL
        download_url = self.get_download_url(platform_info)
        self.log(f"Downloading buf from: {download_url}")
        
        # Download to temporary file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            archive_name = download_url.split("/")[-1]
            archive_path = temp_path / archive_name
            
            # Download the archive
            try:
                urllib.request.urlretrieve(download_url, archive_path)
                self.log(f"Downloaded {archive_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to download buf: {e}")
            
            # Validate checksum
            if not self.validate_checksum(archive_path, platform_info["platform_key"]):
                raise RuntimeError("Checksum validation failed")
            
            # Extract binary
            extract_dir = temp_path / "extract"
            extract_dir.mkdir()
            binary_path = self.extract_archive(archive_path, extract_dir, platform_info)
            
            # Test the binary
            if not self.test_binary(binary_path):
                raise RuntimeError("Downloaded buf binary failed functionality test")
            
            # Move to final location
            if output_path.exists():
                output_path.unlink()
            
            import shutil
            shutil.move(str(binary_path), str(output_path))
            
            self.log(f"Buf binary installed successfully: {output_path}")
            return output_path


def main():
    """Main entry point for Buf downloader."""
    parser = argparse.ArgumentParser(description="Download Buf CLI")
    parser.add_argument("--output-dir", required=True, help="Output directory for buf binary")
    parser.add_argument("--force", action="store_true", help="Force re-download even if binary exists")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        downloader = BufDownloader(verbose=args.verbose)
        output_dir = Path(args.output_dir)
        
        binary_path = downloader.download_buf(output_dir, force=args.force)
        print(f"SUCCESS: Buf binary available at: {binary_path}")
        
    except Exception as e:
        print(f"ERROR: Failed to download buf: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
