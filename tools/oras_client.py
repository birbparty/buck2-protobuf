#!/usr/bin/env python3
"""
ORAS client for protobuf Buck2 integration.

This module provides a unified ORAS client that leverages buck2-oras CLI
for content-addressable artifact management with OCI registries.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re


class OrasClientError(Exception):
    """Base exception for ORAS client operations."""
    pass


class RegistryAuthError(OrasClientError):
    """Registry authentication failed."""
    pass


class ArtifactNotFoundError(OrasClientError):
    """Requested artifact not found in registry."""
    pass


class ContentVerificationError(OrasClientError):
    """Artifact content verification failed."""
    pass


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
        import platform
        
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


class OrasClient:
    """
    Unified ORAS client for buck2-protobuf artifact management.
    
    This client provides a high-level interface for pulling and pushing
    artifacts to OCI registries using the buck2-oras CLI, with content-
    addressable caching and comprehensive error handling.
    """
    
    def __init__(self, registry: str, cache_dir: Union[str, Path], verbose: bool = False):
        """
        Initialize the ORAS client.
        
        Args:
            registry: Registry URL (e.g., "oras.birb.homes")
            cache_dir: Directory to store cached artifacts
            verbose: Enable verbose logging
        """
        self.registry = registry
        self.cache_dir = Path(cache_dir)
        self.verbose = verbose
        
        # Create cache directory structure
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.oras_cache_dir = self.cache_dir / "oras"
        self.oras_cache_dir.mkdir(exist_ok=True)
        self.metadata_cache_dir = self.cache_dir / "metadata"
        self.metadata_cache_dir.mkdir(exist_ok=True)
        
        # Verify buck2-oras CLI is available
        self._verify_dependencies()
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[oras-client] {message}", file=sys.stderr)
    
    def _verify_dependencies(self) -> None:
        """Verify that required tools are available."""
        self.log("Verifying ORAS dependencies...")
        
        # Check buck2-oras CLI
        try:
            result = subprocess.run(
                ["buck2-oras", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise OrasClientError("buck2-oras CLI not functional")
            
            self.log(f"Found buck2-oras: {result.stdout.strip()}")
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise OrasClientError(
                "buck2-oras CLI not found. Please ensure buck2-oras is installed and in PATH"
            ) from e
    
    def _calculate_sha256(self, file_path: Path) -> str:
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
    
    def _get_cache_path(self, digest: str) -> Path:
        """
        Get cache path for a given digest.
        
        Args:
            digest: SHA256 digest of the artifact
            
        Returns:
            Path to cached artifact
        """
        # Use first 2 characters for subdirectory to avoid too many files in one dir
        subdir = digest[:2]
        cache_subdir = self.oras_cache_dir / subdir
        cache_subdir.mkdir(exist_ok=True)
        return cache_subdir / digest
    
    def _get_metadata_path(self, artifact_ref: str) -> Path:
        """
        Get metadata cache path for an artifact reference.
        
        Args:
            artifact_ref: Full artifact reference
            
        Returns:
            Path to metadata file
        """
        # Sanitize artifact reference for filesystem
        safe_ref = re.sub(r'[^\w\-_.]', '_', artifact_ref)
        return self.metadata_cache_dir / f"{safe_ref}.json"
    
    def _parse_digest_from_output(self, output: str) -> Optional[str]:
        """
        Parse digest from buck2-oras pull output.
        
        Args:
            output: Command output text
            
        Returns:
            SHA256 digest if found, None otherwise
        """
        # Look for digest in format: "Digest: sha256:..."
        digest_match = re.search(r"Digest:\s+sha256:([a-f0-9]{64})", output)
        if digest_match:
            return digest_match.group(1)
        return None
    
    def _run_buck2_oras(self, args: List[str], timeout: int = 300) -> subprocess.CompletedProcess:
        """
        Run buck2-oras command with error handling.
        
        Args:
            args: Command arguments (excluding 'buck2-oras')
            timeout: Command timeout in seconds
            
        Returns:
            Completed process result
            
        Raises:
            OrasClientError: If command fails
        """
        cmd = ["buck2-oras"] + args
        if self.verbose:
            cmd.append("--verbose")
        
        self.log(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                stderr = result.stderr.strip()
                
                # Parse specific error types
                if "authentication" in stderr.lower() or "unauthorized" in stderr.lower():
                    raise RegistryAuthError(f"Registry authentication failed: {stderr}")
                elif "not found" in stderr.lower() or "404" in stderr:
                    raise ArtifactNotFoundError(f"Artifact not found: {stderr}")
                else:
                    raise OrasClientError(f"buck2-oras command failed: {stderr}")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            raise OrasClientError(f"buck2-oras command timed out after {timeout}s") from e
    
    def pull(self, artifact_ref: str, expected_digest: Optional[str] = None) -> Path:
        """
        Pull artifact from registry with content verification and caching.
        
        Args:
            artifact_ref: Full artifact reference (registry/repo:tag or @digest)
            expected_digest: Expected SHA256 digest for verification
            
        Returns:
            Path to the cached artifact
            
        Raises:
            OrasClientError: If pull operation fails
            ContentVerificationError: If digest verification fails
            ArtifactNotFoundError: If artifact not found
        """
        self.log(f"Pulling artifact: {artifact_ref}")
        
        # Check if we already have this artifact cached by digest
        if expected_digest:
            cached_path = self._get_cache_path(expected_digest)
            if cached_path.exists():
                self.log(f"Found cached artifact at: {cached_path}")
                return cached_path
        
        # Create temporary directory for pull operation
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Pull artifact using buck2-oras
            pull_args = [
                "pull",
                artifact_ref,
                "-o", str(temp_path),
                "--extract"
            ]
            
            result = self._run_buck2_oras(pull_args)
            
            # Parse digest from output
            digest = self._parse_digest_from_output(result.stderr)
            if not digest:
                self.log("Warning: Could not parse digest from pull output")
            
            # Verify expected digest if provided
            if expected_digest and digest:
                if digest != expected_digest:
                    raise ContentVerificationError(
                        f"Digest mismatch: expected {expected_digest}, got {digest}"
                    )
            
            # Find the main artifact file
            pulled_files = list(temp_path.iterdir())
            if not pulled_files:
                raise OrasClientError("No files were pulled from artifact")
            
            # For protoc-like artifacts, find the binary
            main_artifact = None
            for file in pulled_files:
                if file.is_file() and (file.name == "protoc" or file.name.endswith(".exe")):
                    main_artifact = file
                    break
            
            # If no obvious binary, use the first file
            if not main_artifact:
                main_artifact = next((f for f in pulled_files if f.is_file()), None)
            
            if not main_artifact:
                raise OrasClientError("No valid artifact file found in pulled content")
            
            # Calculate actual digest if not provided
            if not digest:
                digest = self._calculate_sha256(main_artifact)
                self.log(f"Calculated digest: {digest}")
            
            # Verify expected digest if provided (check again with calculated digest)
            if expected_digest and expected_digest != digest:
                raise ContentVerificationError(
                    f"Digest mismatch: expected {expected_digest}, got {digest}"
                )
            
            # Cache the artifact by digest
            cached_path = self._get_cache_path(digest)
            shutil.copy2(main_artifact, cached_path)
            
            # Make executable if it's a binary
            if main_artifact.suffix in ("", ".exe") or "protoc" in main_artifact.name:
                cached_path.chmod(0o755)
            
            # Cache metadata
            metadata = {
                "artifact_ref": artifact_ref,
                "digest": digest,
                "cached_at": time.time(),
                "size": cached_path.stat().st_size,
                "original_name": main_artifact.name
            }
            
            metadata_path = self._get_metadata_path(artifact_ref)
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.log(f"Cached artifact: {cached_path} (digest: {digest})")
            return cached_path
    
    def push(self, files: List[Union[str, Path]], artifact_ref: str, 
             annotations: Optional[Dict[str, str]] = None) -> str:
        """
        Push files as an artifact to the registry.
        
        Args:
            files: List of file paths to include in artifact
            artifact_ref: Target artifact reference
            annotations: Optional OCI annotations
            
        Returns:
            Digest of the pushed artifact
            
        Raises:
            OrasClientError: If push operation fails
        """
        self.log(f"Pushing artifact: {artifact_ref}")
        
        if not files:
            raise OrasClientError("No files provided for push")
        
        # Verify all files exist
        file_paths = []
        for file in files:
            path = Path(file)
            if not path.exists():
                raise OrasClientError(f"File not found: {path}")
            file_paths.append(path)
        
        # Use buck2-oras to push (would need to extend CLI to support raw file push)
        # For now, this is a placeholder for the push functionality
        # In practice, you might need to create a temporary Buck2 target or
        # extend buck2-oras CLI to support direct file push
        
        raise NotImplementedError(
            "Push functionality requires Buck2 target. Use buck2-oras CLI directly for pushing."
        )
    
    def verify_artifact(self, artifact_path: Path, expected_digest: str) -> bool:
        """
        Verify artifact integrity using SHA256 digest.
        
        Args:
            artifact_path: Path to the artifact file
            expected_digest: Expected SHA256 digest
            
        Returns:
            True if verification passes
            
        Raises:
            ContentVerificationError: If verification fails
        """
        if not artifact_path.exists():
            raise ContentVerificationError(f"Artifact not found: {artifact_path}")
        
        actual_digest = self._calculate_sha256(artifact_path)
        
        if actual_digest != expected_digest:
            raise ContentVerificationError(
                f"Digest verification failed for {artifact_path}: "
                f"expected {expected_digest}, got {actual_digest}"
            )
        
        self.log(f"Digest verification passed: {expected_digest}")
        return True
    
    def list_tags(self, repository: str) -> List[str]:
        """
        List available tags in a repository.
        
        Args:
            repository: Repository path (e.g., "test/hello-world")
            
        Returns:
            List of available tags
            
        Raises:
            OrasClientError: If list operation fails
        """
        full_repo = f"{self.registry}/{repository}"
        self.log(f"Listing tags for repository: {full_repo}")
        
        # Use direct oras command since buck2-oras list command has different format
        try:
            result = subprocess.run(
                ["oras", "repo", "tags", full_repo],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise OrasClientError(f"Failed to list tags: {result.stderr}")
            
            tags = [tag.strip() for tag in result.stdout.split('\n') if tag.strip()]
            self.log(f"Found {len(tags)} tags")
            return tags
            
        except subprocess.TimeoutExpired as e:
            raise OrasClientError("Tag listing timed out") from e
        except FileNotFoundError as e:
            raise OrasClientError("ORAS CLI not found") from e
    
    def get_artifact_info(self, artifact_ref: str) -> Dict:
        """
        Get information about an artifact.
        
        Args:
            artifact_ref: Artifact reference
            
        Returns:
            Dictionary with artifact information
        """
        metadata_path = self._get_metadata_path(artifact_ref)
        
        if metadata_path.exists():
            with open(metadata_path) as f:
                return json.load(f)
        
        return {
            "artifact_ref": artifact_ref,
            "cached": False
        }
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cached artifacts.
        
        Args:
            older_than_days: Only clear items older than this many days
            
        Returns:
            Number of items cleared
        """
        cleared = 0
        cutoff_time = time.time() - (older_than_days * 86400) if older_than_days else 0
        
        # Clear ORAS cache
        for cache_subdir in self.oras_cache_dir.iterdir():
            if cache_subdir.is_dir():
                for cached_file in cache_subdir.iterdir():
                    if cached_file.is_file():
                        if not older_than_days or cached_file.stat().st_mtime < cutoff_time:
                            cached_file.unlink()
                            cleared += 1
        
        # Clear metadata cache
        for metadata_file in self.metadata_cache_dir.glob("*.json"):
            if not older_than_days or metadata_file.stat().st_mtime < cutoff_time:
                metadata_file.unlink()
                cleared += 1
        
        self.log(f"Cleared {cleared} cached items")
        return cleared


def detect_platform_string() -> str:
    """
    Detect the current platform and return as a standard string.
    
    Returns:
        Platform string like "linux-x86_64", "darwin-arm64", etc.
    """
    os_name, arch = PlatformDetector.detect()
    return f"{os_name}-{arch}"


def main():
    """Main entry point for ORAS client testing."""
    parser = argparse.ArgumentParser(description="ORAS Client for Buck2 Protobuf")
    parser.add_argument("--registry", default="oras.birb.homes", help="Registry URL")
    parser.add_argument("--cache-dir", required=True, help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Pull command
    pull_parser = subparsers.add_parser("pull", help="Pull artifact")
    pull_parser.add_argument("artifact", help="Artifact reference")
    pull_parser.add_argument("--digest", help="Expected SHA256 digest")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List tags")
    list_parser.add_argument("repository", help="Repository path")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get artifact info")
    info_parser.add_argument("artifact", help="Artifact reference")
    
    # Clear cache command
    clear_parser = subparsers.add_parser("clear-cache", help="Clear cache")
    clear_parser.add_argument("--older-than", type=int, help="Clear items older than N days")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        client = OrasClient(args.registry, args.cache_dir, verbose=args.verbose)
        
        if args.command == "pull":
            result = client.pull(args.artifact, args.digest)
            print(f"Artifact cached at: {result}")
        
        elif args.command == "list":
            tags = client.list_tags(args.repository)
            print(f"Tags for {args.repository}:")
            for tag in tags:
                print(f"  {tag}")
        
        elif args.command == "info":
            info = client.get_artifact_info(args.artifact)
            print(json.dumps(info, indent=2))
        
        elif args.command == "clear-cache":
            cleared = client.clear_cache(args.older_than)
            print(f"Cleared {cleared} cached items")
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
