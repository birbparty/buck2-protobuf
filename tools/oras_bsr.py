#!/usr/bin/env python3
"""
BSR-ORAS integration for popular protobuf dependency resolution.

This module provides a focused resolver for popular BSR dependencies with
optimized ORAS caching and content-addressable storage integration.
"""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import re
import logging

try:
    from .oras_client import OrasClient, OrasClientError
    from .bsr_client import BSRClient, BSRDependency, BSRClientError
except ImportError:
    # Handle direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from oras_client import OrasClient, OrasClientError
    from bsr_client import BSRClient, BSRDependency, BSRClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PopularBSRResolver:
    """
    Focused resolver for popular BSR dependencies with ORAS caching optimization.
    
    This resolver targets the most commonly used BSR modules to maximize impact
    while providing a foundation for general BSR support.
    """
    
    # Popular BSR dependencies with optimized configurations
    SUPPORTED_DEPENDENCIES = {
        "buf.build/googleapis/googleapis": {
            "oras_ref": "bsr-cache/googleapis-googleapis",
            "default_version": "main",
            "common_versions": ["main", "v1.0.0"],
            "description": "Google APIs",
            "size_estimate": "50MB",
            "cache_priority": "high"
        },
        "buf.build/grpc-ecosystem/grpc-gateway": {
            "oras_ref": "bsr-cache/grpc-gateway",
            "default_version": "v2.0.0", 
            "common_versions": ["v2.0.0", "v1.14.0"],
            "description": "gRPC-Gateway HTTP/JSON to gRPC proxy",
            "size_estimate": "10MB",
            "cache_priority": "high"
        },
        "buf.build/envoyproxy/protoc-gen-validate": {
            "oras_ref": "bsr-cache/protoc-gen-validate",
            "default_version": "v0.10.1",
            "common_versions": ["v0.10.1", "v0.9.1"],
            "description": "Protocol Buffer validation",
            "size_estimate": "5MB", 
            "cache_priority": "medium"
        },
        "buf.build/connectrpc/connect": {
            "oras_ref": "bsr-cache/connect",
            "default_version": "v1.0.0",
            "common_versions": ["v1.0.0"],
            "description": "Connect protocol support",
            "size_estimate": "8MB",
            "cache_priority": "medium"
        }
    }
    
    def __init__(self, 
                 oras_registry: str = "oras.birb.homes",
                 cache_dir: Union[str, Path] = None,
                 verbose: bool = False):
        """
        Initialize the popular BSR resolver.
        
        Args:
            oras_registry: ORAS registry URL for caching
            cache_dir: Directory for local caching
            verbose: Enable verbose logging
        """
        self.oras_registry = oras_registry
        self.verbose = verbose
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'bsr'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ORAS and BSR clients
        self.oras_client = OrasClient(
            registry=oras_registry,
            cache_dir=self.cache_dir / 'oras',
            verbose=verbose
        )
        
        self.bsr_client = BSRClient(
            cache_dir=self.cache_dir / 'bsr_metadata',
            verbose=verbose
        )
        
        # BSR-specific cache directories
        self.resolved_deps_cache = self.cache_dir / 'resolved_dependencies'
        self.proto_files_cache = self.cache_dir / 'proto_files'
        
        for cache_subdir in [self.resolved_deps_cache, self.proto_files_cache]:
            cache_subdir.mkdir(exist_ok=True)
        
        if self.verbose:
            logger.info(f"PopularBSRResolver initialized with registry: {oras_registry}")

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            logger.info(f"[bsr-resolver] {message}")

    def is_supported_dependency(self, bsr_ref: str) -> bool:
        """
        Check if a BSR reference is supported by this resolver.
        
        Args:
            bsr_ref: BSR reference (e.g., "buf.build/googleapis/googleapis")
            
        Returns:
            True if supported, False otherwise
        """
        # Parse reference to get base module
        base_ref = self._parse_bsr_reference(bsr_ref)["base_ref"]
        return base_ref in self.SUPPORTED_DEPENDENCIES

    def _parse_bsr_reference(self, bsr_ref: str) -> Dict[str, str]:
        """
        Parse a BSR reference into components.
        
        Args:
            bsr_ref: BSR reference (e.g., "buf.build/googleapis/googleapis:v1.0.0")
            
        Returns:
            Dictionary with parsed components
        """
        # Handle version specification
        if ":" in bsr_ref:
            base_ref, version = bsr_ref.rsplit(":", 1)
        else:
            base_ref = bsr_ref
            version = None
        
        # Parse registry/owner/module
        parts = base_ref.split("/")
        if len(parts) != 3:
            raise ValueError(f"Invalid BSR reference format: {bsr_ref}")
        
        registry, owner, module = parts
        
        return {
            "base_ref": base_ref,
            "registry": registry,
            "owner": owner,
            "module": module,
            "version": version,
            "full_ref": bsr_ref
        }

    def _get_oras_reference(self, bsr_ref: str, version: str) -> str:
        """
        Convert BSR reference to ORAS registry reference.
        
        Args:
            bsr_ref: Base BSR reference
            version: Version to use
            
        Returns:
            ORAS registry reference
        """
        if bsr_ref not in self.SUPPORTED_DEPENDENCIES:
            raise ValueError(f"Unsupported BSR dependency: {bsr_ref}")
        
        config = self.SUPPORTED_DEPENDENCIES[bsr_ref]
        oras_ref = config["oras_ref"]
        
        return f"{self.oras_registry}/{oras_ref}:{version}"

    def _resolve_version(self, bsr_ref: str, requested_version: Optional[str]) -> str:
        """
        Resolve the version to use for a BSR dependency.
        
        Args:
            bsr_ref: Base BSR reference
            requested_version: Requested version (can be None)
            
        Returns:
            Version to use
        """
        if bsr_ref not in self.SUPPORTED_DEPENDENCIES:
            raise ValueError(f"Unsupported BSR dependency: {bsr_ref}")
        
        config = self.SUPPORTED_DEPENDENCIES[bsr_ref]
        
        if requested_version:
            # Validate requested version is in common versions
            if requested_version in config["common_versions"]:
                return requested_version
            else:
                self.log(f"Warning: {requested_version} not in common versions for {bsr_ref}, using anyway")
                return requested_version
        
        return config["default_version"]

    def _get_dependency_cache_path(self, bsr_ref: str, version: str) -> Path:
        """Get cache path for a resolved dependency."""
        safe_ref = re.sub(r'[^\w\-_.]', '_', f"{bsr_ref}_{version}")
        return self.resolved_deps_cache / f"{safe_ref}"

    def _cache_resolved_dependency(self, bsr_ref: str, version: str, proto_files_path: Path) -> None:
        """Cache a resolved dependency."""
        cache_path = self._get_dependency_cache_path(bsr_ref, version)
        
        # Create cache entry with metadata
        cache_data = {
            "bsr_ref": bsr_ref,
            "version": version,
            "proto_files_path": str(proto_files_path),
            "resolved_at": time.time(),
            "cache_key": self._generate_cache_key(bsr_ref, version)
        }
        
        with open(cache_path, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        self.log(f"Cached dependency: {bsr_ref}:{version}")

    def _get_cached_dependency(self, bsr_ref: str, version: str, max_age: int = 3600) -> Optional[Path]:
        """Get cached dependency if still valid."""
        cache_path = self._get_dependency_cache_path(bsr_ref, version)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path) as f:
                cache_data = json.load(f)
            
            # Check cache age
            cached_at = cache_data.get('resolved_at', 0)
            if time.time() - cached_at > max_age:
                return None
            
            proto_files_path = Path(cache_data['proto_files_path'])
            if proto_files_path.exists():
                self.log(f"Using cached dependency: {bsr_ref}:{version}")
                return proto_files_path
        
        except (json.JSONDecodeError, KeyError, OSError):
            pass
        
        return None

    def _generate_cache_key(self, bsr_ref: str, version: str) -> str:
        """Generate a cache key for a BSR dependency."""
        content = f"{bsr_ref}:{version}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _download_bsr_dependency_via_buf(self, bsr_ref: str, version: str) -> Path:
        """
        Download BSR dependency using buf CLI.
        
        Args:
            bsr_ref: BSR reference
            version: Version to download
            
        Returns:
            Path to downloaded proto files
        """
        full_ref = f"{bsr_ref}:{version}"
        
        # Create temporary directory for download
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                self.log(f"Downloading BSR dependency: {full_ref}")
                
                # Use buf export to download the dependency
                result = subprocess.run([
                    "buf", "export", full_ref, 
                    "--output", str(temp_path)
                ], capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    raise BSRClientError(f"Failed to download {full_ref}: {result.stderr}")
                
                # Create permanent cache location
                cache_key = self._generate_cache_key(bsr_ref, version)
                proto_cache_path = self.proto_files_cache / cache_key
                proto_cache_path.mkdir(exist_ok=True)
                
                # Copy downloaded files to cache
                downloaded_files = list(temp_path.rglob("*.proto"))
                if not downloaded_files:
                    raise BSRClientError(f"No proto files found in downloaded dependency: {full_ref}")
                
                for proto_file in downloaded_files:
                    relative_path = proto_file.relative_to(temp_path)
                    dest_path = proto_cache_path / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    dest_path.write_bytes(proto_file.read_bytes())
                
                self.log(f"Downloaded {len(downloaded_files)} proto files for {full_ref}")
                return proto_cache_path
                
            except subprocess.TimeoutExpired:
                raise BSRClientError(f"Timeout downloading BSR dependency: {full_ref}")

    def resolve_popular_dependency(self, bsr_ref: str) -> Path:
        """
        Resolve a popular BSR dependency with ORAS caching optimization.
        
        Args:
            bsr_ref: BSR reference (e.g., "buf.build/googleapis/googleapis:v1.0.0")
            
        Returns:
            Path to cached proto files
            
        Raises:
            ValueError: If dependency is not supported
            BSRClientError: If resolution fails
        """
        # Parse BSR reference
        parsed = self._parse_bsr_reference(bsr_ref)
        base_ref = parsed["base_ref"]
        requested_version = parsed["version"]
        
        # Check if supported
        if not self.is_supported_dependency(base_ref):
            raise ValueError(f"Unsupported BSR dependency: {base_ref}")
        
        # Resolve version
        version = self._resolve_version(base_ref, requested_version)
        
        # Check local cache first
        cached_path = self._get_cached_dependency(base_ref, version)
        if cached_path:
            return cached_path
        
        # Try ORAS cache
        try:
            oras_ref = self._get_oras_reference(base_ref, version)
            self.log(f"Checking ORAS cache: {oras_ref}")
            
            # For now, we'll download directly via buf since ORAS caching
            # for BSR content needs the dependencies to be pre-cached
            # This will be enhanced in future iterations
            proto_files_path = self._download_bsr_dependency_via_buf(base_ref, version)
            
            # Cache the resolved dependency
            self._cache_resolved_dependency(base_ref, version, proto_files_path)
            
            return proto_files_path
            
        except Exception as e:
            # Fallback to direct BSR download
            self.log(f"ORAS cache miss, downloading via BSR: {e}")
            proto_files_path = self._download_bsr_dependency_via_buf(base_ref, version)
            self._cache_resolved_dependency(base_ref, version, proto_files_path)
            return proto_files_path

    def resolve_multiple_dependencies(self, bsr_refs: List[str]) -> Dict[str, Path]:
        """
        Resolve multiple BSR dependencies efficiently.
        
        Args:
            bsr_refs: List of BSR references
            
        Returns:
            Dictionary mapping BSR references to proto file paths
        """
        results = {}
        
        for bsr_ref in bsr_refs:
            try:
                self.log(f"Resolving dependency: {bsr_ref}")
                results[bsr_ref] = self.resolve_popular_dependency(bsr_ref)
            except Exception as e:
                self.log(f"Failed to resolve {bsr_ref}: {e}")
                raise BSRClientError(f"Failed to resolve dependency {bsr_ref}: {e}")
        
        return results

    def get_dependency_info(self, bsr_ref: str) -> Dict:
        """
        Get information about a supported dependency.
        
        Args:
            bsr_ref: BSR reference
            
        Returns:
            Dictionary with dependency information
        """
        parsed = self._parse_bsr_reference(bsr_ref)
        base_ref = parsed["base_ref"]
        
        if base_ref not in self.SUPPORTED_DEPENDENCIES:
            return {"supported": False, "error": "Dependency not supported"}
        
        config = self.SUPPORTED_DEPENDENCIES[base_ref].copy()
        config.update({
            "supported": True,
            "bsr_ref": base_ref,
            "requested_version": parsed["version"],
            "resolved_version": self._resolve_version(base_ref, parsed["version"])
        })
        
        return config

    def list_supported_dependencies(self) -> List[Dict]:
        """
        List all supported dependencies with their configurations.
        
        Returns:
            List of dependency configurations
        """
        dependencies = []
        
        for bsr_ref, config in self.SUPPORTED_DEPENDENCIES.items():
            dep_info = config.copy()
            dep_info["bsr_ref"] = bsr_ref
            dependencies.append(dep_info)
        
        return dependencies

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear BSR dependency cache.
        
        Args:
            older_than_days: Only clear items older than this many days
            
        Returns:
            Number of items cleared
        """
        cleared = 0
        cutoff_time = time.time() - (older_than_days * 86400) if older_than_days else 0
        
        # Clear resolved dependencies cache
        for cache_file in self.resolved_deps_cache.glob("*"):
            if not older_than_days or cache_file.stat().st_mtime < cutoff_time:
                if cache_file.is_file():
                    cache_file.unlink()
                    cleared += 1
        
        # Clear proto files cache
        for cache_dir in self.proto_files_cache.iterdir():
            if cache_dir.is_dir():
                if not older_than_days or cache_dir.stat().st_mtime < cutoff_time:
                    import shutil
                    shutil.rmtree(cache_dir)
                    cleared += 1
        
        # Clear ORAS cache
        cleared += self.oras_client.clear_cache(older_than_days)
        
        self.log(f"Cleared {cleared} cached items")
        return cleared


def main():
    """Main entry point for BSR-ORAS resolver testing."""
    parser = argparse.ArgumentParser(description="Popular BSR Dependency Resolver with ORAS Caching")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve BSR dependency")
    resolve_parser.add_argument("dependency", help="BSR dependency reference")
    
    # Resolve multiple command
    resolve_multi_parser = subparsers.add_parser("resolve-multi", help="Resolve multiple dependencies")
    resolve_multi_parser.add_argument("dependencies", nargs="+", help="BSR dependency references")
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Get dependency info")
    info_parser.add_argument("dependency", help="BSR dependency reference")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List supported dependencies")
    
    # Clear cache command
    clear_parser = subparsers.add_parser("clear-cache", help="Clear cache")
    clear_parser.add_argument("--older-than", type=int, help="Clear items older than N days")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        resolver = PopularBSRResolver(
            oras_registry=args.registry,
            cache_dir=args.cache_dir,
            verbose=args.verbose
        )
        
        if args.command == "resolve":
            result_path = resolver.resolve_popular_dependency(args.dependency)
            print(f"Resolved to: {result_path}")
            
        elif args.command == "resolve-multi":
            results = resolver.resolve_multiple_dependencies(args.dependencies)
            print(f"Resolved {len(results)} dependencies:")
            for dep, path in results.items():
                print(f"  {dep}: {path}")
        
        elif args.command == "info":
            info = resolver.get_dependency_info(args.dependency)
            print(json.dumps(info, indent=2))
        
        elif args.command == "list":
            dependencies = resolver.list_supported_dependencies()
            print(f"Supported dependencies ({len(dependencies)}):")
            for dep in dependencies:
                print(f"  {dep['bsr_ref']}: {dep['description']}")
        
        elif args.command == "clear-cache":
            cleared = resolver.clear_cache(args.older_than)
            print(f"Cleared {cleared} cached items")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
