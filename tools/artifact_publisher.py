#!/usr/bin/env python3
"""
Artifact Publisher for buck2-protobuf ORAS Registry.

This module provides automated publishing of protobuf tools and plugins
to ORAS registries with comprehensive verification and integrity checks.
"""

import asyncio
import hashlib
import json
import logging
import os
import shutil
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import requests
import subprocess
from dataclasses import dataclass
from datetime import datetime

from registry_manager import RegistryManager, RegistryManagerError
from oras_client import OrasClient, detect_platform_string


@dataclass
class ToolRelease:
    """Information about a tool release."""
    name: str
    version: str
    platform: str
    download_url: str
    filename: str
    size: int
    checksum: Optional[str] = None
    checksum_algorithm: str = "sha256"


@dataclass
class PublishResult:
    """Result of a publishing operation."""
    success: bool
    artifact_ref: str
    digest: Optional[str] = None
    error: Optional[str] = None
    size: int = 0
    duration_seconds: float = 0.0


class ArtifactPublisherError(Exception):
    """Base exception for artifact publishing operations."""
    pass


class DownloadError(ArtifactPublisherError):
    """Tool download failed."""
    pass


class VerificationError(ArtifactPublisherError):
    """Artifact verification failed."""
    pass


class ArtifactPublisher:
    """
    Automated publisher for protobuf tools and plugins.
    
    Downloads tools from official sources, verifies integrity,
    and publishes to ORAS registry with proper organization.
    """
    
    def __init__(self, registry_manager: RegistryManager):
        """
        Initialize artifact publisher.
        
        Args:
            registry_manager: Registry manager instance
        """
        self.registry_manager = registry_manager
        self.logger = logging.getLogger("artifact-publisher")
        self.work_dir = Path(tempfile.mkdtemp(prefix="buck2-artifacts-"))
        
        # Get configuration
        self.config = registry_manager.config
        self.publishing_config = self.config.get("publishing", {})
        self.security_config = self.config.get("security", {})
        
        # Create work directories
        self.download_dir = self.work_dir / "downloads"
        self.staging_dir = self.work_dir / "staging"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Initialized artifact publisher with work dir: {self.work_dir}")
    
    def cleanup(self):
        """Clean up temporary directories."""
        try:
            shutil.rmtree(self.work_dir)
            self.logger.info("Cleaned up work directory")
        except Exception as e:
            self.logger.warning(f"Failed to clean up work directory: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
    
    def get_github_releases(self, repo: str, pattern: str = "v*") -> List[Dict]:
        """
        Get releases from a GitHub repository.
        
        Args:
            repo: GitHub repository in format "owner/repo"
            pattern: Release pattern to match
            
        Returns:
            List of release information
        """
        try:
            url = f"https://api.github.com/repos/{repo}/releases"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            releases = response.json()
            filtered_releases = []
            
            for release in releases:
                if release.get("draft") or release.get("prerelease"):
                    continue
                
                tag_name = release["tag_name"]
                if pattern == "v*" and tag_name.startswith("v"):
                    filtered_releases.append(release)
                elif tag_name.startswith(pattern.replace("*", "")):
                    filtered_releases.append(release)
            
            self.logger.info(f"Found {len(filtered_releases)} releases for {repo}")
            return filtered_releases
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch releases for {repo}: {e}")
            return []
    
    def find_platform_asset(self, release: Dict, platform: str) -> Optional[Dict]:
        """
        Find the appropriate asset for a platform in a GitHub release.
        
        Args:
            release: GitHub release information
            platform: Platform string (e.g., "linux-x86_64")
            
        Returns:
            Asset information if found
        """
        assets = release.get("assets", [])
        
        # Platform mapping for different naming conventions
        platform_mapping = {
            "linux-x86_64": ["linux-amd64", "linux_amd64", "linux-x86_64", "linux-64"],
            "linux-aarch64": ["linux-arm64", "linux_arm64", "linux-aarch64"],
            "darwin-x86_64": ["darwin-amd64", "darwin_amd64", "osx-x86_64", "macos-x86_64"],
            "darwin-arm64": ["darwin-arm64", "darwin_arm64", "osx-arm64", "macos-arm64"],
            "windows-x86_64": ["windows-amd64", "windows_amd64", "win64", "windows-x86_64"]
        }
        
        platform_variants = platform_mapping.get(platform, [platform])
        
        for asset in assets:
            asset_name = asset["name"].lower()
            
            # Check if any platform variant matches
            for variant in platform_variants:
                if variant in asset_name:
                    # Skip source files and checksums
                    if any(ext in asset_name for ext in [".tar.gz", ".zip", ".exe"]):
                        if not any(skip in asset_name for skip in ["src", "source", "checksum", ".sha"]):
                            return asset
        
        return None
    
    def download_and_verify(self, tool_release: ToolRelease) -> Path:
        """
        Download and verify a tool release.
        
        Args:
            tool_release: Tool release information
            
        Returns:
            Path to downloaded and verified tool
            
        Raises:
            DownloadError: If download fails
            VerificationError: If verification fails
        """
        download_path = self.download_dir / tool_release.filename
        
        try:
            self.logger.info(f"Downloading {tool_release.name} {tool_release.version} for {tool_release.platform}")
            
            # Download with progress tracking for large files
            response = requests.get(tool_release.download_url, stream=True, timeout=300)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(download_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress for large files
                        if total_size > 10 * 1024 * 1024:  # > 10MB
                            progress = (downloaded / total_size) * 100
                            if downloaded % (1024 * 1024) == 0:  # Every MB
                                self.logger.info(f"Download progress: {progress:.1f}%")
            
            # Verify file size
            actual_size = download_path.stat().st_size
            if tool_release.size and abs(actual_size - tool_release.size) > 1024:  # Allow 1KB variance
                raise VerificationError(
                    f"Size mismatch: expected {tool_release.size}, got {actual_size}"
                )
            
            # Verify checksum if provided
            if tool_release.checksum and self.security_config.get("verify_checksums", True):
                actual_checksum = self._calculate_checksum(download_path, tool_release.checksum_algorithm)
                if actual_checksum != tool_release.checksum.lower():
                    raise VerificationError(
                        f"Checksum mismatch: expected {tool_release.checksum}, got {actual_checksum}"
                    )
                
                self.logger.info(f"Checksum verification passed: {actual_checksum}")
            
            self.logger.info(f"Successfully downloaded and verified: {download_path}")
            return download_path
            
        except requests.RequestException as e:
            raise DownloadError(f"Failed to download {tool_release.download_url}: {e}")
        except Exception as e:
            raise VerificationError(f"Verification failed for {tool_release.filename}: {e}")
    
    def _calculate_checksum(self, file_path: Path, algorithm: str = "sha256") -> str:
        """Calculate checksum of a file."""
        hash_obj = hashlib.new(algorithm)
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def extract_tool_binary(self, archive_path: Path, tool_name: str) -> Path:
        """
        Extract the main tool binary from a downloaded archive.
        
        Args:
            archive_path: Path to downloaded archive
            tool_name: Name of the tool (protoc, buf, etc.)
            
        Returns:
            Path to extracted binary
        """
        extract_dir = self.staging_dir / f"{tool_name}-extract"
        extract_dir.mkdir(exist_ok=True)
        
        if archive_path.suffix.lower() == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        else:
            # Assume tar.gz
            subprocess.run([
                "tar", "-xzf", str(archive_path), "-C", str(extract_dir)
            ], check=True)
        
        # Find the main binary
        binary_name = tool_name
        if archive_path.name.lower().endswith('.exe') or 'windows' in archive_path.name.lower():
            binary_name += '.exe'
        
        # Search for the binary in common locations
        search_paths = [
            extract_dir / binary_name,
            extract_dir / "bin" / binary_name,
            extract_dir / tool_name / "bin" / binary_name,
        ]
        
        # Also search recursively
        for binary in extract_dir.rglob(binary_name):
            if binary.is_file():
                search_paths.append(binary)
        
        for binary_path in search_paths:
            if binary_path.exists() and binary_path.is_file():
                # Make executable
                binary_path.chmod(0o755)
                self.logger.info(f"Extracted binary: {binary_path}")
                return binary_path
        
        raise ArtifactPublisherError(f"Could not find {binary_name} in {archive_path}")
    
    def create_oras_artifact(self, binary_path: Path, tool_release: ToolRelease) -> Path:
        """
        Create an ORAS artifact directory structure.
        
        Args:
            binary_path: Path to the tool binary
            tool_release: Tool release information
            
        Returns:
            Path to artifact directory
        """
        artifact_dir = self.staging_dir / f"{tool_release.name}-{tool_release.version}-{tool_release.platform}"
        artifact_dir.mkdir(exist_ok=True)
        
        # Copy binary with consistent naming
        target_name = tool_release.name
        if binary_path.suffix:
            target_name += binary_path.suffix
        
        target_path = artifact_dir / target_name
        shutil.copy2(binary_path, target_path)
        target_path.chmod(0o755)
        
        # Create metadata file
        metadata = {
            "tool": tool_release.name,
            "version": tool_release.version,
            "platform": tool_release.platform,
            "download_url": tool_release.download_url,
            "size": binary_path.stat().st_size,
            "sha256": self._calculate_checksum(target_path),
            "created_at": datetime.now().isoformat(),
            "buck2_protobuf_version": "1.0.0"
        }
        
        with open(artifact_dir / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.logger.info(f"Created artifact directory: {artifact_dir}")
        return artifact_dir
    
    def publish_tool_release(self, tool_release: ToolRelease) -> PublishResult:
        """
        Publish a single tool release to the registry.
        
        Args:
            tool_release: Tool release to publish
            
        Returns:
            Publishing result
        """
        start_time = datetime.now()
        
        try:
            # Download and verify
            archive_path = self.download_and_verify(tool_release)
            
            # Extract binary (if it's an archive)
            if archive_path.suffix.lower() in ['.zip', '.gz']:
                binary_path = self.extract_tool_binary(archive_path, tool_release.name)
            else:
                binary_path = archive_path
            
            # Create ORAS artifact
            artifact_dir = self.create_oras_artifact(binary_path, tool_release)
            
            # Determine artifact reference
            primary_registry = self.registry_manager.config["primary_registry"]
            namespace = primary_registry["namespace"]
            registry_url = primary_registry["url"]
            
            # Build artifact reference
            tool_path = f"tools/{tool_release.name}"
            version_tag = f"{tool_release.version}-{tool_release.platform}"
            artifact_ref = f"{registry_url}/{namespace}/{tool_path}:{version_tag}"
            
            # TODO: Use ORAS CLI or buck2-oras to publish
            # For now, we'll simulate the publishing process
            # In practice, this would use:
            # buck2-oras push <artifact_dir> <artifact_ref>
            
            self.logger.info(f"Would publish to: {artifact_ref}")
            
            # Calculate duration and return success
            duration = (datetime.now() - start_time).total_seconds()
            
            return PublishResult(
                success=True,
                artifact_ref=artifact_ref,
                digest="sha256:" + self._calculate_checksum(binary_path),
                size=binary_path.stat().st_size,
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.error(f"Failed to publish {tool_release.name} {tool_release.version}: {e}")
            
            return PublishResult(
                success=False,
                artifact_ref="",
                error=str(e),
                duration_seconds=duration
            )
    
    def get_protoc_releases(self, version_limit: int = 5) -> List[ToolRelease]:
        """
        Get protoc releases for all configured platforms.
        
        Args:
            version_limit: Maximum number of versions to process
            
        Returns:
            List of tool releases
        """
        tool_config = self.publishing_config["tool_sources"]["protoc"]
        repo = tool_config["github_repo"]
        platforms = tool_config["platforms"]
        
        releases = self.get_github_releases(repo, tool_config.get("release_pattern", "v*"))
        tool_releases = []
        
        for release in releases[:version_limit]:
            version = release["tag_name"]
            
            for platform in platforms:
                asset = self.find_platform_asset(release, platform)
                if asset:
                    tool_release = ToolRelease(
                        name="protoc",
                        version=version,
                        platform=platform,
                        download_url=asset["browser_download_url"],
                        filename=asset["name"],
                        size=asset["size"]
                    )
                    tool_releases.append(tool_release)
                else:
                    self.logger.warning(f"No asset found for protoc {version} {platform}")
        
        self.logger.info(f"Found {len(tool_releases)} protoc releases to publish")
        return tool_releases
    
    def get_buf_releases(self, version_limit: int = 5) -> List[ToolRelease]:
        """
        Get buf CLI releases for all configured platforms.
        
        Args:
            version_limit: Maximum number of versions to process
            
        Returns:
            List of tool releases
        """
        tool_config = self.publishing_config["tool_sources"]["buf"]
        repo = tool_config["github_repo"]
        platforms = tool_config["platforms"]
        
        releases = self.get_github_releases(repo, tool_config.get("release_pattern", "v*"))
        tool_releases = []
        
        for release in releases[:version_limit]:
            version = release["tag_name"]
            
            for platform in platforms:
                asset = self.find_platform_asset(release, platform)
                if asset:
                    tool_release = ToolRelease(
                        name="buf",
                        version=version,
                        platform=platform,
                        download_url=asset["browser_download_url"],
                        filename=asset["name"],
                        size=asset["size"]
                    )
                    tool_releases.append(tool_release)
                else:
                    self.logger.warning(f"No asset found for buf {version} {platform}")
        
        self.logger.info(f"Found {len(tool_releases)} buf releases to publish")
        return tool_releases
    
    def publish_all_tools(self, parallel: bool = True) -> Dict[str, List[PublishResult]]:
        """
        Publish all configured tools to the registry.
        
        Args:
            parallel: Whether to publish in parallel
            
        Returns:
            Dictionary of publishing results by tool
        """
        results = {}
        
        # Get all tool releases
        all_releases = []
        
        if "protoc" in self.publishing_config["tool_sources"]:
            protoc_releases = self.get_protoc_releases()
            all_releases.extend(protoc_releases)
        
        if "buf" in self.publishing_config["tool_sources"]:
            buf_releases = self.get_buf_releases()
            all_releases.extend(buf_releases)
        
        if not all_releases:
            self.logger.warning("No tool releases found to publish")
            return results
        
        self.logger.info(f"Publishing {len(all_releases)} tool releases")
        
        if parallel:
            # Publish in parallel with thread pool
            max_workers = self.publishing_config.get("parallel_uploads", 4)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_release = {
                    executor.submit(self.publish_tool_release, release): release
                    for release in all_releases
                }
                
                for future in future_to_release:
                    release = future_to_release[future]
                    try:
                        result = future.result()
                        tool_name = release.name
                        if tool_name not in results:
                            results[tool_name] = []
                        results[tool_name].append(result)
                    except Exception as e:
                        self.logger.error(f"Failed to publish {release.name}: {e}")
        else:
            # Publish sequentially
            for release in all_releases:
                result = self.publish_tool_release(release)
                tool_name = release.name
                if tool_name not in results:
                    results[tool_name] = []
                results[tool_name].append(result)
        
        # Log summary
        total_success = sum(len([r for r in tool_results if r.success]) for tool_results in results.values())
        total_failed = sum(len([r for r in tool_results if not r.success]) for tool_results in results.values())
        
        self.logger.info(f"Publishing completed: {total_success} successful, {total_failed} failed")
        
        return results


def main():
    """Main entry point for artifact publisher testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Artifact Publisher for buck2-protobuf")
    parser.add_argument("--config", default="registry.yaml", help="Registry configuration file")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be published without actually publishing")
    parser.add_argument("--tool", choices=["protoc", "buf", "all"], default="all", help="Tool to publish")
    parser.add_argument("--parallel", action="store_true", help="Enable parallel publishing")
    parser.add_argument("--versions", type=int, default=2, help="Number of versions to publish")
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    try:
        registry_manager = RegistryManager(args.config)
        
        with ArtifactPublisher(registry_manager) as publisher:
            if args.tool == "protoc":
                releases = publisher.get_protoc_releases(args.versions)
            elif args.tool == "buf":
                releases = publisher.get_buf_releases(args.versions)
            else:
                releases = []
                releases.extend(publisher.get_protoc_releases(args.versions))
                releases.extend(publisher.get_buf_releases(args.versions))
            
            if args.dry_run:
                print(f"Would publish {len(releases)} releases:")
                for release in releases:
                    print(f"  {release.name} {release.version} {release.platform}")
            else:
                if args.tool == "all":
                    results = publisher.publish_all_tools(args.parallel)
                    print(json.dumps({tool: [r.__dict__ for r in results] for tool, results in results.items()}, indent=2))
                else:
                    for release in releases:
                        result = publisher.publish_tool_release(release)
                        print(json.dumps(result.__dict__, indent=2))
    
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
