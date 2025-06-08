#!/usr/bin/env python3
"""
Publish Buf CLI artifacts to ORAS registry.

This module downloads Buf CLI releases from GitHub and publishes them
to the ORAS registry for distribution via the buck2-protobuf system.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import tarfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Import existing tools
from oras_client import OrasClient
from artifact_publisher import ArtifactPublisher


class BufArtifactPublisher:
    """
    Handles downloading and publishing Buf CLI artifacts to ORAS registry.
    """
    
    def __init__(self, registry: str = "oras.birb.homes", verbose: bool = False):
        """
        Initialize the Buf artifact publisher.
        
        Args:
            registry: ORAS registry URL
            verbose: Enable verbose logging
        """
        self.registry = registry
        self.verbose = verbose
        
        # Initialize ORAS client
        self.oras_client = OrasClient(registry, "/tmp/buf_publisher_cache", verbose=verbose)
        
        # Buf CLI release configuration
        self.supported_versions = ["1.47.2", "1.46.1", "1.45.0"]
        self.github_base_url = "https://github.com/bufbuild/buf/releases/download"
        
        # Platform mapping for Buf CLI releases
        self.platform_mapping = {
            "linux-x86_64": {
                "github_name": "buf-Linux-x86_64.tar.gz",
                "oras_tag": "linux-amd64",
                "binary_name": "buf"
            },
            "linux-aarch64": {
                "github_name": "buf-Linux-aarch64.tar.gz", 
                "oras_tag": "linux-arm64",
                "binary_name": "buf"
            },
            "darwin-x86_64": {
                "github_name": "buf-Darwin-x86_64.tar.gz",
                "oras_tag": "darwin-amd64", 
                "binary_name": "buf"
            },
            "darwin-arm64": {
                "github_name": "buf-Darwin-arm64.tar.gz",
                "oras_tag": "darwin-arm64",
                "binary_name": "buf"
            },
            "windows-x86_64": {
                "github_name": "buf-Windows-x86_64.zip",
                "oras_tag": "windows-amd64",
                "binary_name": "buf.exe"
            }
        }
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[buf-publisher] {message}", file=sys.stderr)
    
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
            for chunk in iter(lambda: f.read(8192), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def download_buf_release(self, version: str, platform: str, output_dir: Path) -> Tuple[Path, str]:
        """
        Download Buf CLI release for a specific version and platform.
        
        Args:
            version: Buf CLI version (e.g., "1.47.2")
            platform: Platform key (e.g., "linux-x86_64")
            output_dir: Directory to save downloaded file
            
        Returns:
            Tuple of (downloaded_file_path, sha256_hash)
            
        Raises:
            ValueError: If version/platform not supported
            RuntimeError: If download fails
        """
        if platform not in self.platform_mapping:
            raise ValueError(f"Unsupported platform: {platform}")
        
        platform_config = self.platform_mapping[platform]
        github_filename = platform_config["github_name"]
        
        # Construct download URL
        download_url = f"{self.github_base_url}/v{version}/{github_filename}"
        
        self.log(f"Downloading Buf CLI {version} for {platform} from {download_url}")
        
        # Download to output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / github_filename
        
        try:
            urllib.request.urlretrieve(download_url, output_file)
            
            # Calculate SHA256
            sha256_hash = self.calculate_sha256(output_file)
            
            self.log(f"Downloaded {output_file} (SHA256: {sha256_hash})")
            return output_file, sha256_hash
            
        except Exception as e:
            raise RuntimeError(f"Failed to download {download_url}: {e}")
    
    def extract_buf_binary(self, archive_path: Path, platform: str, extract_dir: Path) -> Path:
        """
        Extract Buf CLI binary from downloaded archive.
        
        Args:
            archive_path: Path to downloaded archive
            platform: Platform key
            extract_dir: Directory to extract to
            
        Returns:
            Path to extracted buf binary
            
        Raises:
            RuntimeError: If extraction fails
        """
        platform_config = self.platform_mapping[platform]
        binary_name = platform_config["binary_name"]
        
        self.log(f"Extracting {archive_path}")
        
        extract_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            if archive_path.suffix == ".zip":
                # Windows ZIP file
                with zipfile.ZipFile(archive_path, 'r') as zip_file:
                    zip_file.extractall(extract_dir)
            else:
                # Unix tar.gz file
                with tarfile.open(archive_path, 'r:gz') as tar_file:
                    tar_file.extractall(extract_dir)
            
            # Find the buf binary
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == binary_name:
                        binary_path = Path(root) / file
                        
                        # Make executable on Unix systems
                        if binary_name == "buf":
                            os.chmod(binary_path, 0o755)
                        
                        self.log(f"Extracted buf binary: {binary_path}")
                        return binary_path
            
            raise RuntimeError(f"Buf binary '{binary_name}' not found in extracted files")
            
        except Exception as e:
            raise RuntimeError(f"Failed to extract {archive_path}: {e}")
    
    def test_buf_binary(self, binary_path: Path, expected_version: str) -> bool:
        """
        Test that the extracted binary works and has the correct version.
        
        Args:
            binary_path: Path to buf binary
            expected_version: Expected version string
            
        Returns:
            True if test passes, False otherwise
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
                self.log(f"buf --version failed: {result.stderr}")
                return False
            
            version_output = result.stdout.strip()
            if expected_version not in version_output:
                self.log(f"Version mismatch: expected {expected_version}, got {version_output}")
                return False
            
            self.log(f"Buf binary test passed: {version_output}")
            return True
            
        except Exception as e:
            self.log(f"Error testing buf binary: {e}")
            return False
    
    def publish_to_registry(self, binary_path: Path, version: str, platform: str) -> bool:
        """
        Publish Buf CLI binary to ORAS registry.
        
        Args:
            binary_path: Path to buf binary
            version: Buf CLI version
            platform: Platform key
            
        Returns:
            True if publishing succeeds, False otherwise
        """
        platform_config = self.platform_mapping[platform]
        oras_tag = platform_config["oras_tag"]
        
        # Construct ORAS reference
        oras_ref = f"{self.registry}/buck2-protobuf/tools/buf:{version}-{oras_tag}"
        
        self.log(f"Publishing to {oras_ref}")
        
        try:
            # Create temporary directory with the binary
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                bin_dir = temp_path / "bin"
                bin_dir.mkdir()
                
                # Copy binary to standardized location
                target_binary = bin_dir / platform_config["binary_name"]
                shutil.copy2(binary_path, target_binary)
                
                # Create metadata
                metadata = {
                    "version": version,
                    "platform": platform,
                    "oras_tag": oras_tag,
                    "binary_name": platform_config["binary_name"],
                    "sha256": self.calculate_sha256(target_binary)
                }
                
                metadata_file = temp_path / "metadata.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Use ArtifactPublisher for actual publishing
                publisher = ArtifactPublisher(self.registry, verbose=self.verbose)
                
                # Publish directory contents
                success = publisher.publish_directory(
                    temp_path,
                    oras_ref,
                    annotations={
                        "org.opencontainers.image.title": f"Buf CLI {version}",
                        "org.opencontainers.image.version": version,
                        "org.opencontainers.image.description": f"Buf CLI binary for {platform}",
                        "io.buf.platform": platform,
                        "io.buf.version": version
                    }
                )
                
                if success:
                    self.log(f"Successfully published {oras_ref}")
                else:
                    self.log(f"Failed to publish {oras_ref}")
                
                return success
                
        except Exception as e:
            self.log(f"Error publishing to registry: {e}")
            return False
    
    def download_buf_releases(self, versions: List[str] = None) -> Dict[str, Dict]:
        """
        Download Buf CLI releases for all supported platforms.
        
        Args:
            versions: List of versions to download (default: all supported)
            
        Returns:
            Dictionary mapping version -> platform -> artifact info
        """
        if versions is None:
            versions = self.supported_versions
        
        artifacts = {}
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            for version in versions:
                self.log(f"Processing Buf CLI version {version}")
                artifacts[version] = {}
                
                for platform in self.platform_mapping.keys():
                    try:
                        # Download release
                        download_dir = temp_path / version / platform / "download"
                        archive_path, sha256_hash = self.download_buf_release(
                            version, platform, download_dir
                        )
                        
                        # Extract binary
                        extract_dir = temp_path / version / platform / "extract"
                        binary_path = self.extract_buf_binary(
                            archive_path, platform, extract_dir
                        )
                        
                        # Test binary
                        if not self.test_buf_binary(binary_path, version):
                            self.log(f"Binary test failed for {version}/{platform}")
                            continue
                        
                        # Store artifact info
                        artifacts[version][platform] = {
                            "binary_path": binary_path,
                            "archive_path": archive_path,
                            "archive_sha256": sha256_hash,
                            "binary_sha256": self.calculate_sha256(binary_path),
                            "tested": True
                        }
                        
                        self.log(f"Successfully prepared {version}/{platform}")
                        
                    except Exception as e:
                        self.log(f"Failed to process {version}/{platform}: {e}")
                        continue
        
        return artifacts
    
    def publish_all_artifacts(self, artifacts: Dict[str, Dict]) -> bool:
        """
        Publish all downloaded artifacts to ORAS registry.
        
        Args:
            artifacts: Artifact dictionary from download_buf_releases()
            
        Returns:
            True if all publishes succeed, False otherwise
        """
        all_success = True
        
        for version, platforms in artifacts.items():
            for platform, artifact_info in platforms.items():
                if not artifact_info.get("tested", False):
                    self.log(f"Skipping untested artifact {version}/{platform}")
                    continue
                
                success = self.publish_to_registry(
                    artifact_info["binary_path"],
                    version,
                    platform
                )
                
                if not success:
                    all_success = False
                    self.log(f"Failed to publish {version}/{platform}")
        
        return all_success
    
    def verify_published_artifacts(self, versions: List[str] = None) -> bool:
        """
        Verify that published artifacts can be pulled from registry.
        
        Args:
            versions: List of versions to verify (default: all supported)
            
        Returns:
            True if all artifacts can be pulled, False otherwise
        """
        if versions is None:
            versions = self.supported_versions
        
        all_success = True
        
        for version in versions:
            for platform in self.platform_mapping.keys():
                platform_config = self.platform_mapping[platform]
                oras_tag = platform_config["oras_tag"]
                oras_ref = f"{self.registry}/buck2-protobuf/tools/buf:{version}-{oras_tag}"
                
                try:
                    self.log(f"Verifying {oras_ref}")
                    
                    # Try to pull the artifact
                    binary_path = self.oras_client.pull(oras_ref)
                    
                    # Test the pulled binary
                    if not self.test_buf_binary(binary_path, version):
                        self.log(f"Verification failed for {oras_ref}")
                        all_success = False
                    else:
                        self.log(f"Verification passed for {oras_ref}")
                    
                except Exception as e:
                    self.log(f"Failed to verify {oras_ref}: {e}")
                    all_success = False
        
        return all_success
    
    def detect_latest_buf_version(self) -> str:
        """
        Detect the latest Buf CLI version from GitHub API.
        
        Returns:
            Latest version string
            
        Raises:
            RuntimeError: If detection fails
        """
        try:
            api_url = "https://api.github.com/repos/bufbuild/buf/releases/latest"
            
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode())
                
            tag_name = data["tag_name"]
            # Remove 'v' prefix if present
            version = tag_name.lstrip('v')
            
            self.log(f"Detected latest Buf version: {version}")
            return version
            
        except Exception as e:
            raise RuntimeError(f"Failed to detect latest Buf version: {e}")
    
    def get_github_release_info(self, version: str) -> Dict:
        """
        Get detailed information about a Buf CLI release from GitHub.
        
        Args:
            version: Version to get info for
            
        Returns:
            Dictionary with release information
            
        Raises:
            RuntimeError: If API call fails
        """
        try:
            api_url = f"https://api.github.com/repos/bufbuild/buf/releases/tags/v{version}"
            
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode())
            
            # Extract relevant information
            release_info = {
                "tag_name": data["tag_name"],
                "name": data["name"],
                "published_at": data["published_at"],
                "body": data["body"],
                "assets": []
            }
            
            # Process assets
            for asset in data["assets"]:
                release_info["assets"].append({
                    "name": asset["name"],
                    "download_url": asset["browser_download_url"],
                    "size": asset["size"]
                })
            
            return release_info
            
        except Exception as e:
            raise RuntimeError(f"Failed to get release info for {version}: {e}")


def main():
    """Main entry point for Buf CLI artifact publisher."""
    parser = argparse.ArgumentParser(description="Publish Buf CLI artifacts to ORAS registry")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--versions", nargs="+", help="Specific versions to publish")
    parser.add_argument("--verify-only", action="store_true", help="Only verify existing artifacts")
    parser.add_argument("--detect-latest", action="store_true", help="Detect latest version")
    parser.add_argument("--dry-run", action="store_true", help="Download but don't publish")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        publisher = BufArtifactPublisher(
            registry=args.registry,
            verbose=args.verbose
        )
        
        # Handle detect latest version
        if args.detect_latest:
            latest_version = publisher.detect_latest_buf_version()
            print(f"Latest Buf CLI version: {latest_version}")
            
            # Show release info
            release_info = publisher.get_github_release_info(latest_version)
            print(f"Release: {release_info['name']}")
            print(f"Published: {release_info['published_at']}")
            return
        
        # Handle verification only
        if args.verify_only:
            success = publisher.verify_published_artifacts(args.versions)
            if success:
                print("All artifacts verified successfully")
                sys.exit(0)
            else:
                print("Some artifacts failed verification", file=sys.stderr)
                sys.exit(1)
        
        # Download artifacts
        artifacts = publisher.download_buf_releases(args.versions)
        
        if not artifacts:
            print("No artifacts downloaded", file=sys.stderr)
            sys.exit(1)
        
        # Show summary
        total_artifacts = sum(len(platforms) for platforms in artifacts.values())
        print(f"Downloaded {total_artifacts} artifacts for {len(artifacts)} versions")
        
        # Publish unless dry run
        if not args.dry_run:
            success = publisher.publish_all_artifacts(artifacts)
            
            if success:
                print("All artifacts published successfully")
                
                # Verify published artifacts
                if publisher.verify_published_artifacts(list(artifacts.keys())):
                    print("All published artifacts verified")
                    sys.exit(0)
                else:
                    print("Some published artifacts failed verification", file=sys.stderr)
                    sys.exit(1)
            else:
                print("Some artifacts failed to publish", file=sys.stderr)
                sys.exit(1)
        else:
            print("Dry run completed successfully")
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
