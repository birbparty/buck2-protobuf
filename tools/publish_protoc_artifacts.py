#!/usr/bin/env python3
"""
Publisher script for protoc artifacts to ORAS registry.

This script downloads protoc binaries from GitHub and publishes them to
ORAS registry with proper tagging and metadata for the buck2-protobuf
ORAS distribution system.
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
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

# Import our existing tools
sys.path.insert(0, str(Path(__file__).parent))
from download_protoc import ProtocDownloader
from oras_protoc import ProtocOrasDistributor


class ProtocArtifactPublisher:
    """
    Publisher for protoc artifacts to ORAS registry.
    
    This publisher downloads protoc binaries from GitHub releases and
    publishes them to ORAS registry with proper metadata and tagging.
    """
    
    def __init__(self, registry: str = "oras.birb.homes", temp_dir: str = None, verbose: bool = False):
        """
        Initialize the publisher.
        
        Args:
            registry: ORAS registry URL
            temp_dir: Temporary directory for downloads
            verbose: Enable verbose logging
        """
        self.registry = registry
        self.verbose = verbose
        
        if temp_dir is None:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="protoc-publisher-"))
        else:
            self.temp_dir = Path(temp_dir)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        self.downloads_dir = self.temp_dir / "downloads"
        self.downloads_dir.mkdir(exist_ok=True)
        
        # Create downloader for getting artifacts
        self.downloader = ProtocDownloader(str(self.downloads_dir), verbose=verbose)
        
        # Get protoc configuration from our distributor
        distributor = ProtocOrasDistributor(registry=registry, verbose=verbose)
        self.protoc_artifacts = distributor.protoc_artifacts
        
        # Track published artifacts
        self.published_artifacts = []
        self.failed_publishes = []
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[protoc-publisher] {message}", file=sys.stderr)
    
    def verify_prerequisites(self) -> bool:
        """
        Verify that required tools are available.
        
        Returns:
            True if all prerequisites are met
        """
        self.log("Verifying prerequisites...")
        
        # Check for oras CLI
        try:
            result = subprocess.run(
                ["oras", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                print("ERROR: oras CLI not functional", file=sys.stderr)
                return False
            self.log(f"Found oras CLI: {result.stdout.strip()}")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            print("ERROR: oras CLI not found. Please install oras CLI", file=sys.stderr)
            return False
        
        # Check registry connectivity
        try:
            result = subprocess.run(
                ["oras", "repo", "ls", self.registry],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode != 0:
                print(f"WARNING: Cannot list registry {self.registry}: {result.stderr}", file=sys.stderr)
                print("Continuing anyway - registry might not support listing", file=sys.stderr)
            else:
                self.log(f"Registry connectivity verified: {self.registry}")
        except subprocess.TimeoutExpired:
            print(f"WARNING: Registry connectivity test timed out: {self.registry}", file=sys.stderr)
        
        return True
    
    def download_protoc_binary(self, version: str, platform: str) -> Optional[Path]:
        """
        Download protoc binary for specified version and platform.
        
        Args:
            version: Protoc version
            platform: Target platform
            
        Returns:
            Path to downloaded binary, or None if failed
        """
        try:
            self.log(f"Downloading protoc {version} for {platform}")
            binary_path = self.downloader.download_protoc(version, platform)
            return Path(binary_path)
            
        except Exception as e:
            self.log(f"Failed to download protoc {version} {platform}: {e}")
            return None
    
    def create_oci_manifest(self, binary_path: Path, version: str, platform: str) -> Dict:
        """
        Create OCI manifest for protoc binary.
        
        Args:
            binary_path: Path to protoc binary
            version: Protoc version
            platform: Target platform
            
        Returns:
            OCI manifest dictionary
        """
        # Calculate file hash
        sha256_hash = hashlib.sha256()
        with open(binary_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        
        digest = f"sha256:{sha256_hash.hexdigest()}"
        size = binary_path.stat().st_size
        
        # Parse platform for OCI
        os_name, arch = platform.split('-', 1)
        if arch == "aarch64":
            arch = "arm64"  # OCI standard
        elif arch == "x86_64":
            arch = "amd64"  # OCI standard
        
        # Create manifest
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.oci.image.config.v1+json",
                "size": 0,
                "digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # empty config
            },
            "layers": [
                {
                    "mediaType": "application/vnd.oci.image.layer.v1.tar",
                    "size": size,
                    "digest": digest,
                    "annotations": {
                        "org.opencontainers.image.title": "protoc",
                        "org.opencontainers.image.version": version,
                        "org.buck2.protobuf.binary.name": "protoc.exe" if os_name == "windows" else "protoc",
                        "org.buck2.protobuf.binary.platform": platform,
                        "org.buck2.protobuf.binary.executable": "true"
                    }
                }
            ],
            "annotations": {
                "org.opencontainers.image.created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "org.opencontainers.image.title": f"protoc-{version}",
                "org.opencontainers.image.description": f"Protocol Buffer Compiler v{version} for {platform}",
                "org.opencontainers.image.version": version,
                "org.opencontainers.image.vendor": "buck2-protobuf",
                "org.opencontainers.image.url": "https://github.com/protocolbuffers/protobuf",
                "org.opencontainers.image.source": f"https://github.com/protocolbuffers/protobuf/releases/tag/v{version}",
                "org.buck2.protobuf.platform": platform,
                "org.buck2.protobuf.binary.type": "protoc",
                "org.buck2.protobuf.artifact.version": version
            },
            "platform": {
                "architecture": arch,
                "os": os_name
            }
        }
        
        return manifest
    
    def publish_binary_to_registry(self, binary_path: Path, version: str, platform: str) -> bool:
        """
        Publish protoc binary to ORAS registry.
        
        Args:
            binary_path: Path to protoc binary
            version: Protoc version
            platform: Target platform
            
        Returns:
            True if successful, False otherwise
        """
        # Parse platform for OCI
        os_name, arch = platform.split('-', 1)
        if arch == "aarch64":
            arch = "arm64"  # OCI standard
        elif arch == "x86_64":
            arch = "amd64"  # OCI standard
        
        # Create registry reference
        registry_ref = f"{self.registry}/buck2-protobuf/tools/protoc:{version}-{os_name}-{arch}"
        
        self.log(f"Publishing {binary_path} to {registry_ref}")
        
        # Create temporary directory for publishing
        with tempfile.TemporaryDirectory() as pub_dir:
            pub_path = Path(pub_dir)
            
            # Copy binary to publishing directory with standard name
            binary_name = "protoc.exe" if os_name == "windows" else "protoc"
            target_binary = pub_path / binary_name
            shutil.copy2(binary_path, target_binary)
            
            # Make executable
            target_binary.chmod(0o755)
            
            # Create annotations
            annotations = [
                f"org.opencontainers.image.title=protoc-{version}",
                f"org.opencontainers.image.description=Protocol Buffer Compiler v{version} for {platform}",
                f"org.opencontainers.image.version={version}",
                f"org.opencontainers.image.vendor=buck2-protobuf",
                f"org.opencontainers.image.created={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                f"org.buck2.protobuf.platform={platform}",
                f"org.buck2.protobuf.binary.type=protoc",
                f"org.buck2.protobuf.artifact.version={version}",
                f"org.buck2.protobuf.binary.name={binary_name}",
            ]
            
            # Build oras push command
            cmd = [
                "oras", "push", registry_ref,
                f"{target_binary}:application/vnd.buck2.protobuf.binary"
            ]
            
            # Add annotations
            for annotation in annotations:
                cmd.extend(["--annotation", annotation])
            
            # Add platform specification
            cmd.extend(["--platform", f"{os_name}/{arch}"])
            
            if self.verbose:
                cmd.append("--verbose")
            
            try:
                self.log(f"Executing: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    cwd=pub_path,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes
                )
                
                if result.returncode == 0:
                    self.log(f"Successfully published {registry_ref}")
                    self.published_artifacts.append({
                        "version": version,
                        "platform": platform,
                        "registry_ref": registry_ref,
                        "size": binary_path.stat().st_size,
                        "published_at": time.time()
                    })
                    return True
                else:
                    self.log(f"Failed to publish {registry_ref}: {result.stderr}")
                    self.failed_publishes.append({
                        "version": version,
                        "platform": platform,
                        "registry_ref": registry_ref,
                        "error": result.stderr
                    })
                    return False
                    
            except subprocess.TimeoutExpired:
                self.log(f"Timeout publishing {registry_ref}")
                return False
            except Exception as e:
                self.log(f"Error publishing {registry_ref}: {e}")
                return False
    
    def publish_version_platform(self, version: str, platform: str) -> bool:
        """
        Publish single version/platform combination.
        
        Args:
            version: Protoc version
            platform: Target platform
            
        Returns:
            True if successful
        """
        self.log(f"Publishing protoc {version} for {platform}")
        
        # Download binary
        binary_path = self.download_protoc_binary(version, platform)
        if not binary_path:
            return False
        
        # Publish to registry
        return self.publish_binary_to_registry(binary_path, version, platform)
    
    def publish_all_artifacts(self, versions: List[str] = None, platforms: List[str] = None) -> Dict:
        """
        Publish all or specified protoc artifacts.
        
        Args:
            versions: List of versions to publish (all if None)
            platforms: List of platforms to publish (all if None)
            
        Returns:
            Dictionary with publishing statistics
        """
        if versions is None:
            versions = list(self.protoc_artifacts.keys())
        
        if platforms is None:
            # Get all platforms from first version
            first_version = list(self.protoc_artifacts.keys())[0]
            platforms = list(self.protoc_artifacts[first_version].keys())
        
        total_artifacts = len(versions) * len(platforms)
        successful = 0
        failed = 0
        
        self.log(f"Publishing {total_artifacts} artifacts ({len(versions)} versions × {len(platforms)} platforms)")
        
        for version in versions:
            if version not in self.protoc_artifacts:
                self.log(f"Skipping unknown version: {version}")
                continue
                
            for platform in platforms:
                if platform not in self.protoc_artifacts[version]:
                    self.log(f"Skipping unsupported platform {platform} for version {version}")
                    continue
                
                if self.publish_version_platform(version, platform):
                    successful += 1
                else:
                    failed += 1
                
                # Brief pause between publishes to avoid overwhelming registry
                time.sleep(1)
        
        return {
            "total_artifacts": total_artifacts,
            "successful": successful,
            "failed": failed,
            "published_artifacts": self.published_artifacts,
            "failed_publishes": self.failed_publishes
        }
    
    def create_alias_tags(self) -> bool:
        """
        Create alias tags like 'latest' pointing to newest version.
        
        Returns:
            True if successful
        """
        # Find latest version (26.1 is currently latest)
        latest_version = "26.1"
        
        # Get all platforms for latest version
        platforms = list(self.protoc_artifacts[latest_version].keys())
        
        for platform in platforms:
            os_name, arch = platform.split('-', 1)
            if arch == "aarch64":
                arch = "arm64"
            elif arch == "x86_64":
                arch = "amd64"
            
            source_ref = f"{self.registry}/buck2-protobuf/tools/protoc:{latest_version}-{os_name}-{arch}"
            latest_ref = f"{self.registry}/buck2-protobuf/tools/protoc:latest-{os_name}-{arch}"
            
            try:
                # Copy source to latest tag
                cmd = ["oras", "cp", source_ref, latest_ref]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    self.log(f"Created alias {latest_ref} -> {source_ref}")
                else:
                    self.log(f"Failed to create alias {latest_ref}: {result.stderr}")
                    return False
                    
            except Exception as e:
                self.log(f"Error creating alias {latest_ref}: {e}")
                return False
        
        return True
    
    def cleanup(self) -> None:
        """Clean up temporary directories."""
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                self.log(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            self.log(f"Failed to cleanup {self.temp_dir}: {e}")


def main():
    """Main entry point for protoc artifact publishing."""
    parser = argparse.ArgumentParser(description="Publish protoc artifacts to ORAS registry")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--versions", nargs="+", help="Specific versions to publish")
    parser.add_argument("--platforms", nargs="+", help="Specific platforms to publish")
    parser.add_argument("--temp-dir", help="Temporary directory for downloads")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be published")
    parser.add_argument("--create-aliases", action="store_true", help="Create alias tags like 'latest'")
    parser.add_argument("--skip-verify", action="store_true", help="Skip prerequisites verification")
    
    args = parser.parse_args()
    
    try:
        publisher = ProtocArtifactPublisher(
            registry=args.registry,
            temp_dir=args.temp_dir,
            verbose=args.verbose
        )
        
        # Verify prerequisites
        if not args.skip_verify and not publisher.verify_prerequisites():
            print("Prerequisites verification failed. Use --skip-verify to continue anyway.", file=sys.stderr)
            return 1
        
        if args.dry_run:
            print("DRY RUN - would publish:")
            versions = args.versions or list(publisher.protoc_artifacts.keys())
            platforms = args.platforms or list(next(iter(publisher.protoc_artifacts.values())).keys())
            
            for version in versions:
                for platform in platforms:
                    if platform in publisher.protoc_artifacts.get(version, {}):
                        os_name, arch = platform.split('-', 1)
                        if arch == "aarch64":
                            arch = "arm64"
                        elif arch == "x86_64":
                            arch = "amd64"
                        ref = f"{args.registry}/buck2-protobuf/tools/protoc:{version}-{os_name}-{arch}"
                        print(f"  {ref}")
            return 0
        
        # Publish artifacts
        results = publisher.publish_all_artifacts(
            versions=args.versions,
            platforms=args.platforms
        )
        
        # Create aliases if requested
        if args.create_aliases:
            if publisher.create_alias_tags():
                print("Successfully created alias tags")
            else:
                print("Failed to create some alias tags")
        
        # Report results
        print(f"\nPublishing Results:")
        print(f"  Total artifacts: {results['total_artifacts']}")
        print(f"  Successful: {results['successful']}")
        print(f"  Failed: {results['failed']}")
        
        if results['failed_publishes']:
            print(f"\nFailed publishes:")
            for failure in results['failed_publishes']:
                print(f"  {failure['version']} {failure['platform']}: {failure['error']}")
        
        if results['published_artifacts']:
            print(f"\nSuccessfully published artifacts:")
            for artifact in results['published_artifacts']:
                size_mb = artifact['size'] / (1024 * 1024)
                print(f"  {artifact['registry_ref']} ({size_mb:.1f} MB)")
        
        return 0 if results['failed'] == 0 else 1
        
    except KeyboardInterrupt:
        print("\nPublishing interrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Publishing failed: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            publisher.cleanup()
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())
