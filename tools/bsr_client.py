#!/usr/bin/env python3
"""
BSR (Buf Schema Registry) client for team-optimized dependency management.

This module provides a comprehensive BSR client that integrates with team caching
and ORAS infrastructure for optimized dependency resolution and management.
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Union
import re
import hashlib
import logging

try:
    from .bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError
except ImportError:
    # Handle direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class BSRDependency:
    """Represents a BSR dependency with metadata."""
    name: str
    version: str
    digest: str
    repository: str
    commit: Optional[str] = None
    branch: Optional[str] = None
    size: Optional[int] = None
    last_updated: Optional[str] = None
    tags: Optional[List[str]] = None

    def __post_init__(self):
        """Validate and normalize dependency data."""
        if not self.name or not self.version:
            raise ValueError("Dependency name and version are required")
        
        # Normalize version format
        if not self.version.startswith('v'):
            self.version = f"v{self.version}"
        
        # Set default values
        if self.tags is None:
            self.tags = []
        
        if self.last_updated is None:
            self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    @property
    def full_name(self) -> str:
        """Get the full dependency name including repository."""
        return f"{self.repository}/{self.name}"

    @property
    def reference(self) -> str:
        """Get the full BSR reference for this dependency."""
        return f"{self.repository}/{self.name}:{self.version}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'BSRDependency':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class BSRModuleInfo:
    """Information about a BSR module."""
    name: str
    repository: str
    description: str
    owner: str
    visibility: str  # public, private, organization
    dependencies: List[BSRDependency]
    latest_version: str
    tags: List[str]
    created_at: str
    updated_at: str

    def get_dependency_by_name(self, name: str) -> Optional[BSRDependency]:
        """Get a specific dependency by name."""
        for dep in self.dependencies:
            if dep.name == name:
                return dep
        return None


class BSRClientError(Exception):
    """Base exception for BSR client operations."""
    pass


class BSRDependencyNotFoundError(BSRClientError):
    """BSR dependency not found."""
    pass


class BSRModuleNotFoundError(BSRClientError):
    """BSR module not found."""
    pass


class BSRClient:
    """
    Comprehensive BSR client for team-optimized dependency management.
    
    This client provides high-level operations for interacting with the Buf Schema
    Registry, including dependency resolution, module management, and team collaboration.
    """
    
    def __init__(self, 
                 registry_url: str = "buf.build",
                 team: str = None,
                 auth_token: str = None,
                 cache_dir: Union[str, Path] = None,
                 verbose: bool = False,
                 auto_authenticate: bool = True):
        """
        Initialize the BSR client.
        
        Args:
            registry_url: BSR registry URL (default: buf.build)
            team: Team name for team-specific operations
            auth_token: Authentication token for private registries
            cache_dir: Directory for caching BSR metadata
            verbose: Enable verbose logging
            auto_authenticate: Automatically authenticate when needed
        """
        self.registry_url = registry_url
        self.team = team
        self.auth_token = auth_token or os.getenv('BSR_TOKEN')
        self.verbose = verbose
        self.auto_authenticate = auto_authenticate
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'bsr'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache subdirectories
        self.metadata_cache = self.cache_dir / 'metadata'
        self.dependency_cache = self.cache_dir / 'dependencies'
        self.module_cache = self.cache_dir / 'modules'
        
        for cache_subdir in [self.metadata_cache, self.dependency_cache, self.module_cache]:
            cache_subdir.mkdir(exist_ok=True)
        
        # Initialize BSR authenticator
        auth_cache_dir = self.cache_dir / 'auth'
        self.authenticator = BSRAuthenticator(
            cache_dir=auth_cache_dir,
            registry=self.registry_url,
            verbose=self.verbose
        )
        
        # Current authentication credentials
        self._current_credentials: Optional[BSRCredentials] = None
        
        # Verify buf CLI is available
        self._verify_buf_cli()
        
        # Attempt initial authentication if auto_authenticate is enabled
        if self.auto_authenticate:
            try:
                self._ensure_authenticated()
            except BSRAuthenticationError:
                # Don't fail initialization if authentication fails
                # Authentication will be attempted again when needed
                self.log("Initial authentication failed, will retry when needed")
        
        if self.verbose:
            logger.info(f"BSR client initialized for registry: {self.registry_url}")
            if self.team:
                logger.info(f"Team context: {self.team}")

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            logger.info(f"[bsr-client] {message}")

    def _ensure_authenticated(self, repository: str = None) -> BSRCredentials:
        """
        Ensure client is authenticated for BSR access.
        
        Args:
            repository: Repository to authenticate for (optional)
            
        Returns:
            BSR credentials
            
        Raises:
            BSRAuthenticationError: If authentication fails
        """
        target_repo = repository or self.registry_url
        
        # Check if we already have valid credentials
        if self._current_credentials and not self._current_credentials.is_expired():
            if self._current_credentials.registry == target_repo:
                return self._current_credentials
        
        # Authenticate using the authenticator
        try:
            self._current_credentials = self.authenticator.authenticate(repository=target_repo)
            self.log(f"Successfully authenticated for {target_repo}")
            return self._current_credentials
        except BSRAuthenticationError as e:
            self.log(f"Authentication failed for {target_repo}: {e}")
            raise

    def authenticate(self, repository: str = None, method: str = "auto", **kwargs) -> BSRCredentials:
        """
        Explicitly authenticate with BSR.
        
        Args:
            repository: Repository to authenticate for
            method: Authentication method to use
            **kwargs: Additional authentication parameters
            
        Returns:
            BSR credentials
        """
        target_repo = repository or self.registry_url
        
        self._current_credentials = self.authenticator.authenticate(
            repository=target_repo,
            method=method,
            **kwargs
        )
        
        self.log(f"Authenticated for {target_repo} using {method}")
        return self._current_credentials

    def logout(self, repository: str = None) -> bool:
        """
        Logout and clear stored credentials.
        
        Args:
            repository: Repository to logout from (None for all)
            
        Returns:
            True if credentials were cleared
        """
        success = self.authenticator.logout(repository)
        
        # Clear current credentials if they match
        if self._current_credentials:
            target_repo = repository or self.registry_url
            if not repository or self._current_credentials.registry == target_repo:
                self._current_credentials = None
        
        return success

    def get_authentication_status(self, repository: str = None) -> Dict:
        """
        Get authentication status for a repository.
        
        Args:
            repository: Repository to check
            
        Returns:
            Authentication status information
        """
        return self.authenticator.get_authentication_status(repository or self.registry_url)

    def _verify_buf_cli(self) -> None:
        """Verify that buf CLI is available and functional."""
        try:
            result = subprocess.run(
                ["buf", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise BSRClientError("buf CLI not functional")
            
            self.log(f"Found buf CLI: {result.stdout.strip()}")
            
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            raise BSRClientError(
                "buf CLI not found. Please install buf CLI: https://buf.build/docs/installation"
            ) from e

    def _run_buf_command(self, args: List[str], timeout: int = 60, require_auth: bool = False) -> subprocess.CompletedProcess:
        """
        Run a buf command with error handling and authentication.
        
        Args:
            args: Command arguments (excluding 'buf')
            timeout: Command timeout in seconds
            require_auth: Whether authentication is required for this command
            
        Returns:
            Completed process result
            
        Raises:
            BSRClientError: If command fails
        """
        cmd = ["buf"] + args
        
        # Set up environment
        env = os.environ.copy()
        
        # Try to get authentication credentials
        credentials = None
        if require_auth or self.auto_authenticate:
            try:
                credentials = self._ensure_authenticated()
            except BSRAuthenticationError as e:
                if require_auth:
                    raise
                else:
                    self.log(f"Authentication failed, proceeding without: {e}")
        
        # Add authentication to environment
        if credentials:
            env['BUF_TOKEN'] = credentials.token
        elif self.auth_token:
            env['BUF_TOKEN'] = self.auth_token
        
        self.log(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env
            )
            
            if result.returncode != 0:
                stderr = result.stderr.strip()
                
                # Parse specific error types
                if "authentication" in stderr.lower() or "unauthorized" in stderr.lower():
                    # If we got an auth error and auto_authenticate is enabled, try once more
                    if self.auto_authenticate and not require_auth:
                        try:
                            self.log("Authentication failed, attempting to re-authenticate")
                            credentials = self._ensure_authenticated()
                            env['BUF_TOKEN'] = credentials.token
                            
                            # Retry the command with new credentials
                            result = subprocess.run(
                                cmd,
                                capture_output=True,
                                text=True,
                                timeout=timeout,
                                env=env
                            )
                            
                            if result.returncode == 0:
                                return result
                            
                        except BSRAuthenticationError:
                            pass
                    
                    raise BSRAuthenticationError(f"BSR authentication failed: {stderr}")
                elif "not found" in stderr.lower() or "404" in stderr:
                    raise BSRDependencyNotFoundError(f"Dependency not found: {stderr}")
                else:
                    raise BSRClientError(f"buf command failed: {stderr}")
            
            return result
            
        except subprocess.TimeoutExpired as e:
            raise BSRClientError(f"buf command timed out after {timeout}s") from e

    def _get_metadata_cache_path(self, key: str) -> Path:
        """Get cache path for metadata."""
        safe_key = re.sub(r'[^\w\-_.]', '_', key)
        return self.metadata_cache / f"{safe_key}.json"

    def _cache_metadata(self, key: str, data: Dict) -> None:
        """Cache metadata to disk."""
        cache_path = self._get_metadata_cache_path(key)
        data['_cached_at'] = time.time()
        with open(cache_path, 'w') as f:
            json.dump(data, f, indent=2)

    def _get_cached_metadata(self, key: str, max_age: int = 3600) -> Optional[Dict]:
        """Get cached metadata if still valid."""
        cache_path = self._get_metadata_cache_path(key)
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path) as f:
                data = json.load(f)
            
            cached_at = data.get('_cached_at', 0)
            if time.time() - cached_at < max_age:
                return data
        except (json.JSONDecodeError, KeyError):
            pass
        
        return None

    def parse_buf_yaml(self, buf_yaml_path: Path) -> Dict:
        """
        Parse buf.yaml file to extract dependency information.
        
        Args:
            buf_yaml_path: Path to buf.yaml file
            
        Returns:
            Dictionary containing parsed buf.yaml information
            
        Raises:
            BSRClientError: If parsing fails
        """
        if not buf_yaml_path.exists():
            raise BSRClientError(f"buf.yaml not found: {buf_yaml_path}")
        
        try:
            import yaml
            with open(buf_yaml_path) as f:
                buf_config = yaml.safe_load(f)
            
            self.log(f"Parsed buf.yaml: {buf_yaml_path}")
            return buf_config
            
        except ImportError:
            raise BSRClientError("PyYAML required for buf.yaml parsing. Install with: pip install PyYAML")
        except yaml.YAMLError as e:
            raise BSRClientError(f"Failed to parse buf.yaml: {e}")

    def resolve_dependencies(self, buf_yaml_path: Path) -> List[BSRDependency]:
        """
        Resolve dependencies from buf.yaml file.
        
        Args:
            buf_yaml_path: Path to buf.yaml file
            
        Returns:
            List of resolved BSR dependencies
        """
        buf_config = self.parse_buf_yaml(buf_yaml_path)
        dependencies = []
        
        # Extract dependencies from buf.yaml
        deps = buf_config.get('deps', [])
        if not deps:
            self.log("No dependencies found in buf.yaml")
            return dependencies
        
        for dep in deps:
            try:
                # Parse dependency reference (e.g., "buf.build/googleapis/googleapis:v1.0.0")
                if isinstance(dep, str):
                    dep_ref = dep
                elif isinstance(dep, dict):
                    dep_ref = dep.get('name', '')
                else:
                    continue
                
                # Parse the reference
                parts = dep_ref.split('/')
                if len(parts) < 3:
                    self.log(f"Skipping invalid dependency reference: {dep_ref}")
                    continue
                
                registry = parts[0]
                owner = parts[1]
                name_version = parts[2]
                
                if ':' in name_version:
                    name, version = name_version.split(':', 1)
                else:
                    name = name_version
                    version = "latest"
                
                dependency = BSRDependency(
                    name=name,
                    version=version,
                    digest="",  # Will be resolved later
                    repository=f"{registry}/{owner}",
                    tags=["dependency"]
                )
                
                dependencies.append(dependency)
                self.log(f"Found dependency: {dependency.reference}")
                
            except Exception as e:
                self.log(f"Error parsing dependency {dep}: {e}")
                continue
        
        return dependencies

    def get_dependency_metadata(self, dep: BSRDependency) -> Dict:
        """
        Get detailed metadata for a dependency.
        
        Args:
            dep: BSR dependency
            
        Returns:
            Dictionary containing dependency metadata
        """
        cache_key = f"dep_metadata_{dep.reference}"
        
        # Check cache first
        cached_data = self._get_cached_metadata(cache_key)
        if cached_data:
            self.log(f"Using cached metadata for {dep.reference}")
            return cached_data
        
        try:
            # Use buf CLI to get dependency info
            result = self._run_buf_command([
                "registry", "repository", "info",
                dep.repository,
                "--format", "json"
            ])
            
            metadata = json.loads(result.stdout)
            
            # Enhance with additional information
            metadata.update({
                'dependency_name': dep.name,
                'dependency_version': dep.version,
                'full_reference': dep.reference,
                'resolved_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            })
            
            # Cache the metadata
            self._cache_metadata(cache_key, metadata)
            
            self.log(f"Retrieved metadata for {dep.reference}")
            return metadata
            
        except Exception as e:
            self.log(f"Failed to get metadata for {dep.reference}: {e}")
            return {
                'dependency_name': dep.name,
                'dependency_version': dep.version,
                'full_reference': dep.reference,
                'error': str(e),
                'resolved_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }

    def download_dependency(self, dep: BSRDependency, output_dir: Path) -> Path:
        """
        Download a dependency to the specified directory.
        
        Args:
            dep: BSR dependency to download
            output_dir: Directory to download to
            
        Returns:
            Path to downloaded dependency
            
        Raises:
            BSRClientError: If download fails
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create unique directory for this dependency
        dep_dir = output_dir / f"{dep.name}-{dep.version}"
        dep_dir.mkdir(exist_ok=True)
        
        try:
            self.log(f"Downloading dependency: {dep.reference}")
            
            # Use buf CLI to download the dependency
            result = self._run_buf_command([
                "export",
                dep.reference,
                "--output", str(dep_dir)
            ])
            
            self.log(f"Downloaded {dep.reference} to {dep_dir}")
            return dep_dir
            
        except Exception as e:
            raise BSRClientError(f"Failed to download dependency {dep.reference}: {e}")

    def list_repository_modules(self, repository: str) -> List[Dict]:
        """
        List all modules in a repository.
        
        Args:
            repository: Repository name (e.g., "buf.build/googleapis")
            
        Returns:
            List of module information dictionaries
        """
        cache_key = f"repo_modules_{repository}"
        
        # Check cache first
        cached_data = self._get_cached_metadata(cache_key, max_age=1800)  # 30 minutes
        if cached_data:
            return cached_data.get('modules', [])
        
        try:
            result = self._run_buf_command([
                "registry", "repository", "list",
                repository,
                "--format", "json"
            ])
            
            modules_data = json.loads(result.stdout)
            
            # Cache the results
            self._cache_metadata(cache_key, {
                'repository': repository,
                'modules': modules_data,
                'count': len(modules_data)
            })
            
            self.log(f"Listed {len(modules_data)} modules in {repository}")
            return modules_data
            
        except Exception as e:
            self.log(f"Failed to list modules in {repository}: {e}")
            return []

    def search_modules(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search for modules across the BSR.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching modules
        """
        try:
            result = self._run_buf_command([
                "registry", "search",
                query,
                "--limit", str(limit),
                "--format", "json"
            ])
            
            search_results = json.loads(result.stdout)
            self.log(f"Found {len(search_results)} modules for query: {query}")
            return search_results
            
        except Exception as e:
            self.log(f"Search failed for query '{query}': {e}")
            return []

    def get_module_info(self, module_reference: str) -> Optional[BSRModuleInfo]:
        """
        Get detailed information about a module.
        
        Args:
            module_reference: Full module reference
            
        Returns:
            BSRModuleInfo object or None if not found
        """
        cache_key = f"module_info_{module_reference}"
        
        # Check cache first
        cached_data = self._get_cached_metadata(cache_key)
        if cached_data:
            # Convert cached data back to BSRModuleInfo
            dependencies = [BSRDependency.from_dict(dep) for dep in cached_data.get('dependencies', [])]
            cached_data['dependencies'] = dependencies
            return BSRModuleInfo(**cached_data)
        
        try:
            result = self._run_buf_command([
                "registry", "module", "info",
                module_reference,
                "--format", "json"
            ])
            
            module_data = json.loads(result.stdout)
            
            # Create BSRModuleInfo object
            module_info = BSRModuleInfo(
                name=module_data.get('name', ''),
                repository=module_data.get('repository', ''),
                description=module_data.get('description', ''),
                owner=module_data.get('owner', ''),
                visibility=module_data.get('visibility', 'public'),
                dependencies=[],  # Will be populated separately if needed
                latest_version=module_data.get('latest_version', ''),
                tags=module_data.get('tags', []),
                created_at=module_data.get('created_at', ''),
                updated_at=module_data.get('updated_at', '')
            )
            
            # Cache the module info
            cache_data = asdict(module_info)
            self._cache_metadata(cache_key, cache_data)
            
            self.log(f"Retrieved module info: {module_reference}")
            return module_info
            
        except Exception as e:
            self.log(f"Failed to get module info for {module_reference}: {e}")
            return None

    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cached BSR metadata.
        
        Args:
            older_than_days: Only clear items older than this many days
            
        Returns:
            Number of items cleared
        """
        cleared = 0
        cutoff_time = time.time() - (older_than_days * 86400) if older_than_days else 0
        
        for cache_dir in [self.metadata_cache, self.dependency_cache, self.module_cache]:
            for cache_file in cache_dir.glob("*.json"):
                if not older_than_days or cache_file.stat().st_mtime < cutoff_time:
                    cache_file.unlink()
                    cleared += 1
        
        self.log(f"Cleared {cleared} cached items")
        return cleared

    def get_team_dependencies(self) -> List[BSRDependency]:
        """
        Get dependencies commonly used by the team.
        
        Returns:
            List of team dependencies (placeholder implementation)
        """
        # This is a placeholder - in a real implementation, this would
        # query team usage data from the infrastructure
        if not self.team:
            return []
        
        # Mock team dependencies for demonstration
        team_deps = [
            BSRDependency(
                name="googleapis",
                version="v1.0.0",
                digest="sha256:example",
                repository="buf.build/googleapis",
                tags=["team", "common"]
            ),
            BSRDependency(
                name="grpc-gateway",
                version="v2.0.0", 
                digest="sha256:example",
                repository="buf.build/grpc-ecosystem",
                tags=["team", "gateway"]
            )
        ]
        
        self.log(f"Retrieved {len(team_deps)} team dependencies")
        return team_deps


def main():
    """Main entry point for BSR client testing."""
    parser = argparse.ArgumentParser(description="BSR Client for Team-Optimized Dependency Management")
    parser.add_argument("--registry", default="buf.build", help="BSR registry URL")
    parser.add_argument("--team", help="Team name")
    parser.add_argument("--token", help="Authentication token")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve dependencies from buf.yaml")
    resolve_parser.add_argument("buf_yaml", help="Path to buf.yaml file")
    
    # Download command
    download_parser = subparsers.add_parser("download", help="Download a dependency")
    download_parser.add_argument("reference", help="Dependency reference")
    download_parser.add_argument("--output", "-o", required=True, help="Output directory")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Search modules")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--limit", type=int, default=20, help="Result limit")
    
    # Module info command
    info_parser = subparsers.add_parser("info", help="Get module info")
    info_parser.add_argument("module", help="Module reference")
    
    # Team dependencies command
    team_parser = subparsers.add_parser("team-deps", help="Get team dependencies")
    
    # Clear cache command
    clear_parser = subparsers.add_parser("clear-cache", help="Clear cache")
    clear_parser.add_argument("--older-than", type=int, help="Clear items older than N days")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        client = BSRClient(
            registry_url=args.registry,
            team=args.team,
            auth_token=args.token,
            cache_dir=args.cache_dir,
            verbose=args.verbose
        )
        
        if args.command == "resolve":
            buf_yaml_path = Path(args.buf_yaml)
            dependencies = client.resolve_dependencies(buf_yaml_path)
            print(f"Resolved {len(dependencies)} dependencies:")
            for dep in dependencies:
                print(f"  {dep.reference}")
        
        elif args.command == "download":
            # Parse reference to create BSRDependency
            parts = args.reference.split('/')
            if len(parts) >= 3 and ':' in parts[2]:
                name, version = parts[2].split(':', 1)
                dep = BSRDependency(
                    name=name,
                    version=version,
                    digest="",
                    repository='/'.join(parts[:2])
                )
                output_path = client.download_dependency(dep, Path(args.output))
                print(f"Downloaded to: {output_path}")
            else:
                print("Invalid dependency reference format")
        
        elif args.command == "search":
            results = client.search_modules(args.query, args.limit)
            print(f"Found {len(results)} modules:")
            for result in results:
                print(f"  {result.get('name', 'N/A')}: {result.get('description', 'No description')}")
        
        elif args.command == "info":
            info = client.get_module_info(args.module)
            if info:
                print(f"Module: {info.name}")
                print(f"Repository: {info.repository}")
                print(f"Description: {info.description}")
                print(f"Owner: {info.owner}")
                print(f"Latest Version: {info.latest_version}")
            else:
                print("Module not found")
        
        elif args.command == "team-deps":
            if not args.team:
                print("Team name required for team dependencies")
                return
            dependencies = client.get_team_dependencies()
            print(f"Team dependencies for {args.team}:")
            for dep in dependencies:
                print(f"  {dep.reference}")
        
        elif args.command == "clear-cache":
            cleared = client.clear_cache(args.older_than)
            print(f"Cleared {cleared} cached items")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
