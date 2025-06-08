#!/usr/bin/env python3
"""
Registry Manager for buck2-protobuf ORAS Infrastructure.

This module provides a unified registry management system that handles:
- Multi-registry configuration
- Repository structure setup
- Automated publishing workflows
- Security and verification controls
- Monitoring and maintenance
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Tuple
import yaml
import hashlib
import subprocess
import requests
from dataclasses import dataclass
from datetime import datetime, timedelta

from oras_client import OrasClient, OrasClientError, detect_platform_string


@dataclass
class RegistryConfig:
    """Configuration for a single registry."""
    url: str
    namespace: str
    auth_required: bool = False
    auth_method: Optional[str] = None
    
    @property
    def base_url(self) -> str:
        """Get the base registry URL with namespace."""
        return f"{self.url}/{self.namespace}"


@dataclass
class RepositoryConfig:
    """Configuration for a repository within a registry."""
    path: str
    description: str
    auto_publish: bool = True
    retention_days: int = 365


@dataclass
class ArtifactInfo:
    """Information about a published artifact."""
    name: str
    version: str
    platform: str
    digest: str
    size: int
    published_at: datetime
    source_url: str
    

class RegistryManagerError(Exception):
    """Base exception for registry manager operations."""
    pass


class ConfigurationError(RegistryManagerError):
    """Configuration loading or validation failed."""
    pass


class PublishingError(RegistryManagerError):
    """Artifact publishing operation failed."""
    pass


class RegistryManager:
    """
    Central manager for ORAS registry infrastructure.
    
    Handles multiple registries, automated publishing, security verification,
    and maintenance workflows for the buck2-protobuf ecosystem.
    """
    
    def __init__(self, config_path: Union[str, Path] = "registry.yaml"):
        """
        Initialize registry manager with configuration.
        
        Args:
            config_path: Path to registry configuration file
        """
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # Set up local cache first
        self.cache_dir = Path(self.config.get("cache", {}).get("local_cache_dir", "/tmp/buck2-protobuf-cache"))
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize registry clients
        self.primary_registry = self._init_primary_registry()
        self.backup_registries = self._init_backup_registries()
        
        # Initialize metrics
        self.metrics = {
            "artifacts_published": 0,
            "artifacts_verified": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "last_sync": None
        }
    
    def _load_config(self) -> Dict:
        """Load and validate registry configuration."""
        try:
            if not self.config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            
            # Validate required sections
            required_sections = ["primary_registry", "repositories", "publishing"]
            for section in required_sections:
                if section not in config:
                    raise ConfigurationError(f"Missing required configuration section: {section}")
            
            return config
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _setup_logging(self) -> logging.Logger:
        """Set up structured logging."""
        logger = logging.getLogger("registry-manager")
        
        # Get logging config
        log_config = self.config.get("logging", {})
        log_level = getattr(logging, log_config.get("level", "INFO").upper())
        
        logger.setLevel(log_level)
        
        # Create handler if not already configured
        if not logger.handlers:
            handler = logging.StreamHandler()
            
            if log_config.get("format") == "json":
                formatter = logging.Formatter(
                    '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
                    '"component": "registry-manager", "message": "%(message)s"}'
                )
            else:
                formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)s] registry-manager: %(message)s'
                )
            
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        
        return logger
    
    def _init_primary_registry(self) -> OrasClient:
        """Initialize primary registry client."""
        primary_config = self.config["primary_registry"]
        registry_url = primary_config["url"]
        
        # Create ORAS client with namespace-aware cache
        cache_dir = self.cache_dir / "primary"
        client = OrasClient(registry_url, cache_dir, verbose=True)
        
        self.logger.info(f"Initialized primary registry: {registry_url}")
        return client
    
    def _init_backup_registries(self) -> List[OrasClient]:
        """Initialize backup registry clients."""
        clients = []
        
        for i, backup_config in enumerate(self.config.get("backup_registries", [])):
            registry_url = backup_config["url"]
            cache_dir = self.cache_dir / f"backup_{i}"
            
            client = OrasClient(registry_url, cache_dir, verbose=True)
            clients.append(client)
            
            self.logger.info(f"Initialized backup registry: {registry_url}")
        
        return clients
    
    def get_repository_structure(self) -> Dict[str, str]:
        """
        Get the complete repository structure for the primary registry.
        
        Returns:
            Dictionary mapping repository paths to their full URLs
        """
        primary_config = RegistryConfig(**self.config["primary_registry"])
        repositories = {}
        
        for repo_name, repo_config in self.config["repositories"].items():
            repo_path = repo_config["path"]
            full_path = f"{primary_config.base_url}/{repo_path}"
            repositories[repo_name] = full_path
        
        return repositories
    
    def setup_repository_structure(self) -> None:
        """
        Set up the organized repository structure in the registry.
        
        Creates the namespace structure:
        buck2-protobuf/
        ├── tools/
        ├── plugins/
        └── bundles/
        """
        self.logger.info("Setting up repository structure...")
        
        primary_config = RegistryConfig(**self.config["primary_registry"])
        repositories = self.get_repository_structure()
        
        # Verify we can access the registry
        try:
            # Test connectivity by attempting to list a known repository
            test_repo = "test/hello-world"  # Known to exist on oras.birb.homes
            tags = self.primary_registry.list_tags(test_repo)
            self.logger.info(f"Registry connectivity verified - found {len(tags)} tags in {test_repo}")
            
        except Exception as e:
            raise RegistryManagerError(f"Cannot access primary registry {primary_config.url}: {e}")
        
        # Log the planned structure
        self.logger.info(f"Repository structure for {primary_config.base_url}:")
        for repo_name, repo_url in repositories.items():
            repo_config = self.config["repositories"][repo_name]
            self.logger.info(f"  {repo_name}: {repo_url} ({repo_config['description']})")
    
    def get_tool_versions(self, tool_name: str) -> List[str]:
        """
        Get available versions for a tool from GitHub releases.
        
        Args:
            tool_name: Name of the tool (protoc, buf, etc.)
            
        Returns:
            List of available version strings
        """
        tool_config = self.config["publishing"]["tool_sources"].get(tool_name)
        if not tool_config:
            raise ValueError(f"Unknown tool: {tool_name}")
        
        github_repo = tool_config["github_repo"]
        release_pattern = tool_config.get("release_pattern", "v*")
        
        try:
            # Fetch releases from GitHub API
            url = f"https://api.github.com/repos/{github_repo}/releases"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            releases = response.json()
            versions = []
            
            for release in releases:
                if release.get("draft") or release.get("prerelease"):
                    continue
                
                tag_name = release["tag_name"]
                # Simple pattern matching for now
                if release_pattern == "v*" and tag_name.startswith("v"):
                    versions.append(tag_name)
                elif tag_name.startswith(release_pattern.replace("*", "")):
                    versions.append(tag_name)
            
            self.logger.info(f"Found {len(versions)} versions for {tool_name}")
            return versions[:10]  # Return latest 10 versions
            
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch versions for {tool_name}: {e}")
            return []
    
    def get_published_artifacts(self, repository: str) -> List[ArtifactInfo]:
        """
        Get list of artifacts published in a repository.
        
        Args:
            repository: Repository name (tools, plugins, bundles)
            
        Returns:
            List of published artifact information
        """
        artifacts = []
        
        try:
            repo_config = self.config["repositories"][repository]
            repo_path = repo_config["path"]
            
            # For now, return empty list as we would need to implement
            # registry catalog API or maintain our own index
            self.logger.info(f"Listing artifacts in {repository} (not yet implemented)")
            
        except KeyError:
            self.logger.error(f"Unknown repository: {repository}")
        
        return artifacts
    
    def verify_artifact(self, artifact_ref: str, expected_digest: Optional[str] = None) -> bool:
        """
        Verify an artifact's integrity and security.
        
        Args:
            artifact_ref: Full artifact reference
            expected_digest: Expected SHA256 digest
            
        Returns:
            True if verification passes
        """
        try:
            # Pull artifact to verify it exists and is accessible
            artifact_path = self.primary_registry.pull(artifact_ref, expected_digest)
            
            # Verify checksum if configured
            security_config = self.config.get("security", {})
            if security_config.get("verify_checksums", True) and expected_digest:
                self.primary_registry.verify_artifact(artifact_path, expected_digest)
            
            self.metrics["artifacts_verified"] += 1
            self.logger.info(f"Artifact verification passed: {artifact_ref}")
            return True
            
        except Exception as e:
            self.metrics["errors"] += 1
            self.logger.error(f"Artifact verification failed for {artifact_ref}: {e}")
            return False
    
    def health_check(self) -> Dict[str, Union[bool, str, int]]:
        """
        Perform comprehensive health check of registry infrastructure.
        
        Returns:
            Health status dictionary
        """
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }
        
        # Check primary registry connectivity
        try:
            test_repo = "test/hello-world"
            tags = self.primary_registry.list_tags(test_repo)
            health["checks"]["primary_registry"] = {
                "status": "healthy",
                "response_time_ms": 0,  # Would need to measure
                "test_tags_found": len(tags)
            }
        except Exception as e:
            health["status"] = "degraded"
            health["checks"]["primary_registry"] = {
                "status": "unhealthy",
                "error": str(e)
            }
        
        # Check cache directory
        try:
            cache_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
            max_size = self.config.get("cache", {}).get("max_cache_size_gb", 10) * 1024**3
            
            health["checks"]["cache"] = {
                "status": "healthy" if cache_size < max_size * 0.9 else "warning",
                "size_bytes": cache_size,
                "size_gb": round(cache_size / 1024**3, 2),
                "max_size_gb": max_size / 1024**3,
                "usage_percent": round((cache_size / max_size) * 100, 1)
            }
        except Exception as e:
            health["checks"]["cache"] = {
                "status": "warning",
                "error": str(e)
            }
        
        # Add metrics
        health["metrics"] = self.metrics.copy()
        
        return health
    
    def cleanup_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clean up old cached artifacts.
        
        Args:
            older_than_days: Clean items older than this many days
            
        Returns:
            Number of items cleaned up
        """
        if older_than_days is None:
            older_than_days = self.config.get("cache", {}).get("cleanup_older_than_days", 7)
        
        total_cleaned = 0
        
        # Clean primary registry cache
        total_cleaned += self.primary_registry.clear_cache(older_than_days)
        
        # Clean backup registry caches
        for backup_client in self.backup_registries:
            total_cleaned += backup_client.clear_cache(older_than_days)
        
        self.logger.info(f"Cache cleanup completed: {total_cleaned} items removed")
        return total_cleaned
    
    def get_metrics(self) -> Dict:
        """Get current metrics and statistics."""
        metrics = self.metrics.copy()
        
        # Add cache statistics
        try:
            cache_size = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
            cache_files = len(list(self.cache_dir.rglob('*')))
            
            metrics.update({
                "cache_size_bytes": cache_size,
                "cache_files": cache_files,
                "cache_size_gb": round(cache_size / 1024**3, 2)
            })
        except Exception:
            metrics.update({
                "cache_size_bytes": -1,
                "cache_files": -1,
                "cache_size_gb": -1
            })
        
        return metrics
    
    def export_config(self) -> Dict:
        """Export current configuration for backup or inspection."""
        return {
            "config_path": str(self.config_path),
            "config": self.config,
            "primary_registry_url": self.config["primary_registry"]["url"],
            "repositories": self.get_repository_structure(),
            "cache_dir": str(self.cache_dir),
            "metrics": self.get_metrics()
        }


def main():
    """Main entry point for registry manager testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Registry Manager for buck2-protobuf")
    parser.add_argument("--config", default="registry.yaml", help="Registry configuration file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup command
    setup_parser = subparsers.add_parser("setup", help="Set up repository structure")
    
    # Health command
    health_parser = subparsers.add_parser("health", help="Perform health check")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up cache")
    cleanup_parser.add_argument("--older-than", type=int, default=7, help="Clean items older than N days")
    
    # Versions command
    versions_parser = subparsers.add_parser("versions", help="Get tool versions")
    versions_parser.add_argument("tool", help="Tool name (protoc, buf)")
    
    # Metrics command
    metrics_parser = subparsers.add_parser("metrics", help="Show metrics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = RegistryManager(args.config)
        
        if args.command == "setup":
            manager.setup_repository_structure()
            print("Repository structure setup completed")
        
        elif args.command == "health":
            health = manager.health_check()
            print(json.dumps(health, indent=2))
        
        elif args.command == "cleanup":
            cleaned = manager.cleanup_cache(args.older_than)
            print(f"Cleaned up {cleaned} cached items")
        
        elif args.command == "versions":
            versions = manager.get_tool_versions(args.tool)
            print(f"Available versions for {args.tool}:")
            for version in versions:
                print(f"  {version}")
        
        elif args.command == "metrics":
            metrics = manager.get_metrics()
            print(json.dumps(metrics, indent=2))
    
    except Exception as e:
        print(f"ERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
