#!/usr/bin/env python3
"""
BSR Semantic Version Manager.

This module provides intelligent semantic versioning for protobuf schemas
based on change analysis, with support for automatic version increments,
breaking change detection, and multi-registry version consistency.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union
import logging

# Import existing tools
from bsr_auth import BSRAuthenticator
from bsr_client import BSRClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class VersionIncrement(Enum):
    """Types of version increments."""
    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"
    NONE = "none"


class ChangeType(Enum):
    """Types of schema changes."""
    BREAKING = "breaking"
    FEATURE = "feature"
    FIX = "fix"
    DOCS = "docs"
    STYLE = "style"


@dataclass
class SchemaChange:
    """Represents a change in protobuf schema."""
    change_type: ChangeType
    severity: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None


@dataclass
class VersionInfo:
    """Version information with metadata."""
    version: str
    increment_type: VersionIncrement
    base_version: str
    changes: List[SchemaChange]
    change_summary: str
    created_at: float
    git_commit: Optional[str] = None
    git_tag: Optional[str] = None


class BSRVersionManager:
    """
    Intelligent semantic versioning for protobuf schemas.
    
    Provides automatic version detection based on schema changes,
    semantic versioning compliance, and multi-registry coordination.
    """
    
    def __init__(self, 
                 registry: str = "buf.build",
                 cache_dir: Union[str, Path] = None,
                 verbose: bool = False):
        """
        Initialize version manager.
        
        Args:
            registry: Primary BSR registry URL
            cache_dir: Directory for version caching
            verbose: Enable verbose logging
        """
        self.registry = registry
        self.verbose = verbose
        
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'bsr-versions'
        
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize BSR client for version queries
        self.bsr_auth = BSRAuthenticator(verbose=verbose)
        self.bsr_client = BSRClient(registry, verbose=verbose)
        
        # Version patterns
        self.semver_pattern = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)(?:-([a-zA-Z0-9\-\.]+))?(?:\+([a-zA-Z0-9\-\.]+))?$')
        
        # Breaking change patterns (field removal, type changes, etc.)
        self.breaking_patterns = [
            r'removed\s+field',
            r'changed\s+type.*from.*to',
            r'removed\s+service',
            r'removed\s+rpc',
            r'changed\s+field\s+number',
            r'removed\s+enum\s+value',
        ]
        
        if self.verbose:
            logger.info(f"BSR version manager initialized for registry: {self.registry}")

    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            logger.info(f"[bsr-version] {message}")

    def parse_semantic_version(self, version: str) -> Optional[Tuple[int, int, int, str, str]]:
        """
        Parse semantic version string.
        
        Args:
            version: Version string (e.g., "v1.2.3-alpha+build.123")
            
        Returns:
            Tuple of (major, minor, patch, prerelease, build) or None if invalid
        """
        match = self.semver_pattern.match(version)
        if not match:
            return None
        
        major, minor, patch, prerelease, build = match.groups()
        return (
            int(major),
            int(minor), 
            int(patch),
            prerelease or "",
            build or ""
        )

    def format_semantic_version(self, major: int, minor: int, patch: int, 
                               prerelease: str = "", build: str = "") -> str:
        """
        Format semantic version components into string.
        
        Args:
            major: Major version number
            minor: Minor version number 
            patch: Patch version number
            prerelease: Prerelease identifier (optional)
            build: Build metadata (optional)
            
        Returns:
            Formatted semantic version string
        """
        version = f"v{major}.{minor}.{patch}"
        
        if prerelease:
            version += f"-{prerelease}"
        
        if build:
            version += f"+{build}"
        
        return version

    def get_latest_version(self, repository: str) -> Optional[str]:
        """
        Get the latest published version for a repository.
        
        Args:
            repository: BSR repository reference
            
        Returns:
            Latest version string or None if no versions found
        """
        try:
            self.log(f"Querying latest version for {repository}")
            
            # Use BSR client to get repository information
            repo_info = self.bsr_client.get_repository_info(repository)
            
            if repo_info and 'tags' in repo_info:
                versions = []
                
                for tag in repo_info['tags']:
                    parsed = self.parse_semantic_version(tag)
                    if parsed:
                        versions.append((tag, parsed))
                
                if versions:
                    # Sort by semantic version (major, minor, patch)
                    versions.sort(key=lambda x: x[1][:3], reverse=True)
                    latest = versions[0][0]
                    self.log(f"Latest version found: {latest}")
                    return latest
            
            self.log(f"No versions found for {repository}")
            return None
            
        except Exception as e:
            self.log(f"Error querying latest version: {e}")
            return None

    def detect_schema_changes(self, 
                             current_protos: List[Path],
                             baseline_protos: List[Path] = None,
                             baseline_version: str = None) -> List[SchemaChange]:
        """
        Detect changes between current and baseline protobuf schemas.
        
        Args:
            current_protos: List of current protobuf files
            baseline_protos: List of baseline protobuf files (optional)
            baseline_version: Baseline version for comparison (optional)
            
        Returns:
            List of detected schema changes
        """
        changes = []
        
        try:
            # If no baseline provided, try to get from BSR
            if not baseline_protos and baseline_version:
                baseline_protos = self._download_baseline_protos(baseline_version)
            
            if not baseline_protos:
                self.log("No baseline for comparison - treating as initial version")
                return [SchemaChange(
                    change_type=ChangeType.FEATURE,
                    severity="minor",
                    description="Initial schema version",
                    file_path="*"
                )]
            
            # Use buf CLI for breaking change detection
            changes.extend(self._detect_buf_breaking_changes(current_protos, baseline_protos))
            
            # Additional change analysis
            changes.extend(self._detect_file_changes(current_protos, baseline_protos))
            
            self.log(f"Detected {len(changes)} schema changes")
            return changes
            
        except Exception as e:
            self.log(f"Error detecting schema changes: {e}")
            # Return safe default
            return [SchemaChange(
                change_type=ChangeType.PATCH,
                severity="patch",
                description=f"Schema change detection failed: {e}",
                file_path="*"
            )]

    def _detect_buf_breaking_changes(self, 
                                   current_protos: List[Path],
                                   baseline_protos: List[Path]) -> List[SchemaChange]:
        """Use buf CLI to detect breaking changes."""
        changes = []
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create current and baseline directories
                current_dir = temp_path / "current"
                baseline_dir = temp_path / "baseline"
                current_dir.mkdir()
                baseline_dir.mkdir()
                
                # Copy proto files
                for proto in current_protos:
                    if proto.exists():
                        target = current_dir / proto.name
                        target.write_text(proto.read_text())
                
                for proto in baseline_protos:
                    if proto.exists():
                        target = baseline_dir / proto.name
                        target.write_text(proto.read_text())
                
                # Run buf breaking change detection
                cmd = [
                    "buf", "breaking",
                    str(current_dir),
                    "--against", str(baseline_dir),
                    "--format", "json"
                ]
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                
                if result.returncode == 0:
                    self.log("No breaking changes detected by buf")
                elif result.returncode == 1:
                    # Breaking changes found
                    try:
                        breaking_data = json.loads(result.stdout)
                        for issue in breaking_data.get('issues', []):
                            changes.append(SchemaChange(
                                change_type=ChangeType.BREAKING,
                                severity="major",
                                description=issue.get('message', 'Breaking change detected'),
                                file_path=issue.get('path', 'unknown'),
                                line_number=issue.get('start_line'),
                            ))
                    except json.JSONDecodeError:
                        # Fallback to stderr parsing
                        for line in result.stderr.split('\n'):
                            if any(pattern in line.lower() for pattern in self.breaking_patterns):
                                changes.append(SchemaChange(
                                    change_type=ChangeType.BREAKING,
                                    severity="major", 
                                    description=line.strip(),
                                    file_path="unknown"
                                ))
                else:
                    self.log(f"buf breaking command failed: {result.stderr}")
                    
        except subprocess.TimeoutExpired:
            self.log("buf breaking change detection timed out")
        except FileNotFoundError:
            self.log("buf CLI not found - skipping breaking change detection")
        except Exception as e:
            self.log(f"Error running buf breaking change detection: {e}")
        
        return changes

    def _detect_file_changes(self, 
                           current_protos: List[Path],
                           baseline_protos: List[Path]) -> List[SchemaChange]:
        """Detect file-level changes (additions, removals, modifications)."""
        changes = []
        
        # Create sets of file names for comparison
        current_files = {p.name for p in current_protos if p.exists()}
        baseline_files = {p.name for p in baseline_protos if p.exists()}
        
        # New files (feature addition)
        new_files = current_files - baseline_files
        for file_name in new_files:
            changes.append(SchemaChange(
                change_type=ChangeType.FEATURE,
                severity="minor",
                description=f"Added new proto file: {file_name}",
                file_path=file_name
            ))
        
        # Removed files (breaking change)
        removed_files = baseline_files - current_files
        for file_name in removed_files:
            changes.append(SchemaChange(
                change_type=ChangeType.BREAKING,
                severity="major",
                description=f"Removed proto file: {file_name}",
                file_path=file_name
            ))
        
        # Modified files
        common_files = current_files & baseline_files
        for file_name in common_files:
            current_file = next((p for p in current_protos if p.name == file_name), None)
            baseline_file = next((p for p in baseline_protos if p.name == file_name), None)
            
            if current_file and baseline_file and current_file.exists() and baseline_file.exists():
                if current_file.read_text() != baseline_file.read_text():
                    changes.append(SchemaChange(
                        change_type=ChangeType.FIX,  # Default to fix, buf will detect breaking
                        severity="patch",
                        description=f"Modified proto file: {file_name}",
                        file_path=file_name
                    ))
        
        return changes

    def _download_baseline_protos(self, version: str) -> Optional[List[Path]]:
        """Download baseline proto files for comparison."""
        # This would integrate with BSR client to download specific version
        # For now, return None to indicate no baseline available
        self.log(f"Baseline download not implemented for version {version}")
        return None

    def determine_version_increment(self, changes: List[SchemaChange]) -> VersionIncrement:
        """
        Determine appropriate version increment based on detected changes.
        
        Args:
            changes: List of detected schema changes
            
        Returns:
            Recommended version increment type
        """
        if not changes:
            return VersionIncrement.NONE
        
        # Check for breaking changes (major version)
        has_breaking = any(c.change_type == ChangeType.BREAKING for c in changes)
        if has_breaking:
            self.log("Breaking changes detected - recommending MAJOR version increment")
            return VersionIncrement.MAJOR
        
        # Check for new features (minor version)
        has_features = any(c.change_type == ChangeType.FEATURE for c in changes)
        if has_features:
            self.log("New features detected - recommending MINOR version increment")
            return VersionIncrement.MINOR
        
        # Everything else is patch level
        self.log("Only fixes/patches detected - recommending PATCH version increment")
        return VersionIncrement.PATCH

    def generate_next_version(self,
                            current_version: Optional[str],
                            increment: VersionIncrement,
                            prerelease: str = "",
                            build: str = "") -> str:
        """
        Generate the next semantic version.
        
        Args:
            current_version: Current version (None for initial)
            increment: Type of version increment
            prerelease: Prerelease identifier (optional)
            build: Build metadata (optional)
            
        Returns:
            Next semantic version string
        """
        if not current_version or increment == VersionIncrement.NONE:
            if not current_version:
                # Initial version
                return self.format_semantic_version(1, 0, 0, prerelease, build)
            else:
                return current_version
        
        # Parse current version
        parsed = self.parse_semantic_version(current_version)
        if not parsed:
            # Invalid current version, start fresh
            self.log(f"Invalid current version format: {current_version}")
            return self.format_semantic_version(1, 0, 0, prerelease, build)
        
        major, minor, patch, _, _ = parsed
        
        # Apply increment
        if increment == VersionIncrement.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif increment == VersionIncrement.MINOR:
            minor += 1
            patch = 0
        elif increment == VersionIncrement.PATCH:
            patch += 1
        
        next_version = self.format_semantic_version(major, minor, patch, prerelease, build)
        self.log(f"Generated next version: {current_version} -> {next_version}")
        
        return next_version

    def validate_version_consistency(self, 
                                   version: str,
                                   repositories: Dict[str, str]) -> Dict[str, bool]:
        """
        Validate version consistency across multiple registries.
        
        Args:
            version: Version to validate
            repositories: Dictionary of registry name -> repository URL
            
        Returns:
            Dictionary of registry name -> consistency status
        """
        consistency = {}
        
        for registry_name, repository in repositories.items():
            try:
                self.log(f"Checking version consistency for {registry_name}: {repository}")
                
                # Get latest version from this registry
                latest = self.get_latest_version(repository)
                
                if latest:
                    # Compare with proposed version
                    latest_parsed = self.parse_semantic_version(latest)
                    version_parsed = self.parse_semantic_version(version)
                    
                    if latest_parsed and version_parsed:
                        # Version should be greater than latest
                        latest_tuple = latest_parsed[:3]
                        version_tuple = version_parsed[:3]
                        
                        is_consistent = version_tuple > latest_tuple
                        consistency[registry_name] = is_consistent
                        
                        if not is_consistent:
                            self.log(f"Version inconsistency in {registry_name}: {version} <= {latest}")
                    else:
                        # Can't parse versions, assume inconsistent
                        consistency[registry_name] = False
                else:
                    # No existing versions, any version is consistent
                    consistency[registry_name] = True
                    
            except Exception as e:
                self.log(f"Error checking consistency for {registry_name}: {e}")
                consistency[registry_name] = False
        
        return consistency

    def create_version_info(self,
                          proto_files: List[Path],
                          baseline_version: str = None,
                          repositories: Dict[str, str] = None,
                          prerelease: str = "",
                          build: str = "") -> VersionInfo:
        """
        Create comprehensive version information with change analysis.
        
        Args:
            proto_files: List of protobuf files to analyze
            baseline_version: Baseline version for comparison
            repositories: Dictionary of registries for consistency checking
            prerelease: Prerelease identifier
            build: Build metadata
            
        Returns:
            Complete version information
        """
        self.log(f"Creating version info for {len(proto_files)} proto files")
        
        # Get current latest version
        if repositories:
            current_version = None
            for repository in repositories.values():
                version = self.get_latest_version(repository)
                if version:
                    current_version = version
                    break
        else:
            current_version = baseline_version
        
        # Detect schema changes
        changes = self.detect_schema_changes(
            current_protos=proto_files,
            baseline_version=current_version
        )
        
        # Determine version increment
        increment = self.determine_version_increment(changes)
        
        # Generate next version
        next_version = self.generate_next_version(
            current_version=current_version,
            increment=increment,
            prerelease=prerelease,
            build=build
        )
        
        # Create change summary
        change_summary = self._create_change_summary(changes)
        
        # Get git information if available
        git_commit = self._get_git_commit()
        git_tag = self._get_git_tag()
        
        version_info = VersionInfo(
            version=next_version,
            increment_type=increment,
            base_version=current_version or "none",
            changes=changes,
            change_summary=change_summary,
            created_at=time.time(),
            git_commit=git_commit,
            git_tag=git_tag
        )
        
        self.log(f"Created version info: {next_version} ({increment.value})")
        return version_info

    def _create_change_summary(self, changes: List[SchemaChange]) -> str:
        """Create a human-readable change summary."""
        if not changes:
            return "No changes detected"
        
        breaking = [c for c in changes if c.change_type == ChangeType.BREAKING]
        features = [c for c in changes if c.change_type == ChangeType.FEATURE]
        fixes = [c for c in changes if c.change_type == ChangeType.FIX]
        
        summary_parts = []
        
        if breaking:
            summary_parts.append(f"{len(breaking)} breaking changes")
        if features:
            summary_parts.append(f"{len(features)} new features")
        if fixes:
            summary_parts.append(f"{len(fixes)} fixes")
        
        return ", ".join(summary_parts)

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _get_git_tag(self) -> Optional[str]:
        """Get current git tag if on a tagged commit."""
        try:
            result = subprocess.run(
                ["git", "describe", "--exact-match", "--tags"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def save_version_info(self, version_info: VersionInfo, repository: str) -> Path:
        """
        Save version information to cache.
        
        Args:
            version_info: Version information to save
            repository: Repository this version info is for
            
        Returns:
            Path to saved version info file
        """
        # Create safe filename from repository
        safe_repo = re.sub(r'[^\w\-_.]', '_', repository)
        filename = f"{safe_repo}_{version_info.version}_{int(version_info.created_at)}.json"
        
        file_path = self.cache_dir / filename
        
        # Convert to serializable format
        data = asdict(version_info)
        data['changes'] = [asdict(change) for change in version_info.changes]
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        self.log(f"Saved version info to {file_path}")
        return file_path

    def load_version_info(self, file_path: Path) -> Optional[VersionInfo]:
        """
        Load version information from cache.
        
        Args:
            file_path: Path to version info file
            
        Returns:
            Loaded version information or None if failed
        """
        try:
            with open(file_path) as f:
                data = json.load(f)
            
            # Reconstruct change objects
            changes = []
            for change_data in data.get('changes', []):
                changes.append(SchemaChange(
                    change_type=ChangeType(change_data['change_type']),
                    severity=change_data['severity'],
                    description=change_data['description'],
                    file_path=change_data['file_path'],
                    line_number=change_data.get('line_number'),
                    field_name=change_data.get('field_name'),
                    old_value=change_data.get('old_value'),
                    new_value=change_data.get('new_value')
                ))
            
            data['changes'] = changes
            data['increment_type'] = VersionIncrement(data['increment_type'])
            
            return VersionInfo(**data)
            
        except Exception as e:
            self.log(f"Error loading version info from {file_path}: {e}")
            return None


def main():
    """Main entry point for BSR version manager testing."""
    parser = argparse.ArgumentParser(description="BSR Semantic Version Manager")
    parser.add_argument("--registry", default="buf.build", help="BSR registry URL")
    parser.add_argument("--repository", required=True, help="Repository to analyze")
    parser.add_argument("--proto-files", nargs="+", required=True, help="Proto files to analyze")
    parser.add_argument("--baseline-version", help="Baseline version for comparison")
    parser.add_argument("--prerelease", help="Prerelease identifier")
    parser.add_argument("--build", help="Build metadata")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        version_manager = BSRVersionManager(
            registry=args.registry,
            verbose=args.verbose
        )
        
        # Convert file paths
        proto_files = [Path(f) for f in args.proto_files]
        
        # Create version info
        version_info = version_manager.create_version_info(
            proto_files=proto_files,
            baseline_version=args.baseline_version,
            repositories={"primary": args.repository},
            prerelease=args.prerelease or "",
            build=args.build or ""
        )
        
        # Display results
        print(f"📦 Version Analysis Results")
        print(f"   Repository: {args.repository}")
        print(f"   Current Version: {version_info.base_version}")
        print(f"   Next Version: {version_info.version}")
        print(f"   Increment Type: {version_info.increment_type.value}")
        print(f"   Changes: {version_info.change_summary}")
        
        if version_info.changes:
            print(f"\n📋 Detected Changes:")
            for i, change in enumerate(version_info.changes, 1):
                print(f"   {i}. {change.change_type.value}: {change.description}")
        
        # Save version info
        saved_path = version_manager.save_version_info(version_info, args.repository)
        print(f"\n💾 Version info saved to: {saved_path}")
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
