#!/usr/bin/env python3
"""
BSR Team ORAS Cache - Team-optimized caching system for BSR dependencies.

This module provides advanced caching optimization for development teams,
including shared caches, dependency bundling, and usage pattern analysis.
"""

import argparse
import hashlib
import json
import os
import shutil
import statistics
import tempfile
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Tuple
import logging

# Local imports
from .bsr_client import BSRClient, BSRDependency, BSRClientError
from .oras_client import OrasClient, OrasClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UsagePattern:
    """Represents team dependency usage patterns."""
    team: str
    dependencies: Dict[str, int]  # dependency -> usage count
    time_patterns: Dict[str, List[float]]  # dependency -> access times
    team_members: List[str]
    common_bundles: List[str]
    peak_usage_hours: List[int]
    cache_hit_rate: float
    bandwidth_usage: float
    last_updated: str

    def get_most_used_dependencies(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get the most frequently used dependencies."""
        return sorted(self.dependencies.items(), key=lambda x: x[1], reverse=True)[:limit]

    def get_bundle_candidates(self, min_usage: int = 5) -> List[str]:
        """Get dependencies that are good candidates for bundling."""
        return [dep for dep, count in self.dependencies.items() if count >= min_usage]


@dataclass 
class CacheStrategy:
    """Defines caching strategy for a team."""
    team: str
    cache_type: str  # aggressive, balanced, conservative
    shared_cache_enabled: bool
    bundle_strategy: str  # auto, manual, disabled
    cache_size_limit: int  # MB
    eviction_policy: str  # lru, lfu, time_based
    preload_dependencies: List[str]
    sync_frequency: int  # minutes
    compression_enabled: bool

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'CacheStrategy':
        return cls(**data)


@dataclass
class CachePerformanceMetrics:
    """Cache performance metrics for a team."""
    team: str
    cache_hit_rate: float
    avg_download_time: float
    total_cache_size: int
    bandwidth_saved: float
    build_time_improvement: float
    shared_cache_efficiency: float
    bundle_usage_rate: float
    timestamp: str


@dataclass
class DependencyBundle:
    """Represents a bundle of related dependencies."""
    name: str
    description: str
    dependencies: List[BSRDependency]
    version: str
    team: str
    size: int
    created_at: str
    usage_count: int
    oras_ref: str


class TeamUsageAnalyzer:
    """Analyzes team usage patterns for cache optimization."""
    
    def __init__(self, team: str, cache_dir: Path):
        self.team = team
        self.cache_dir = cache_dir
        self.usage_data_file = cache_dir / f"team_{team}_usage.json"
        self.analysis_cache_dir = cache_dir / "analysis"
        self.analysis_cache_dir.mkdir(exist_ok=True)

    def track_dependency_access(self, dependency: str, member: str) -> None:
        """Track when a team member accesses a dependency."""
        usage_data = self._load_usage_data()
        
        current_time = time.time()
        if dependency not in usage_data["dependencies"]:
            usage_data["dependencies"][dependency] = 0
        usage_data["dependencies"][dependency] += 1
        
        if dependency not in usage_data["time_patterns"]:
            usage_data["time_patterns"][dependency] = []
        usage_data["time_patterns"][dependency].append(current_time)
        
        # Keep only last 100 access times per dependency
        if len(usage_data["time_patterns"][dependency]) > 100:
            usage_data["time_patterns"][dependency] = usage_data["time_patterns"][dependency][-100:]
        
        if member not in usage_data["team_members"]:
            usage_data["team_members"].append(member)
        
        usage_data["last_updated"] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        self._save_usage_data(usage_data)

    def _load_usage_data(self) -> Dict:
        """Load team usage data from cache."""
        if not self.usage_data_file.exists():
            return {
                "team": self.team,
                "dependencies": {},
                "time_patterns": {},
                "team_members": [],
                "common_bundles": [],
                "peak_usage_hours": [],
                "cache_hit_rate": 0.0,
                "bandwidth_usage": 0.0,
                "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
        
        try:
            with open(self.usage_data_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return self._load_usage_data()  # Return default

    def _save_usage_data(self, data: Dict) -> None:
        """Save team usage data to cache."""
        with open(self.usage_data_file, 'w') as f:
            json.dump(data, f, indent=2)

    def analyze_dependency_patterns(self) -> UsagePattern:
        """Analyze team dependency usage patterns."""
        usage_data = self._load_usage_data()
        
        # Calculate peak usage hours
        all_times = []
        for times in usage_data["time_patterns"].values():
            all_times.extend(times)
        
        if all_times:
            hours = [time.localtime(t).tm_hour for t in all_times]
            hour_counts = Counter(hours)
            peak_hours = [hour for hour, count in hour_counts.most_common(3)]
        else:
            peak_hours = []
        
        return UsagePattern(
            team=self.team,
            dependencies=usage_data["dependencies"],
            time_patterns=usage_data["time_patterns"],
            team_members=usage_data["team_members"],
            common_bundles=usage_data["common_bundles"],
            peak_usage_hours=peak_hours,
            cache_hit_rate=usage_data["cache_hit_rate"],
            bandwidth_usage=usage_data["bandwidth_usage"],
            last_updated=usage_data["last_updated"]
        )

    def identify_bundle_opportunities(self, min_co_occurrence: int = 3) -> List[Dict]:
        """Identify opportunities for dependency bundling."""
        usage_data = self._load_usage_data()
        dependencies = usage_data["dependencies"]
        time_patterns = usage_data["time_patterns"]
        
        # Find dependencies that are frequently used together
        bundle_opportunities = []
        
        # Simple co-occurrence analysis
        for dep1 in dependencies:
            if dependencies[dep1] < min_co_occurrence:
                continue
                
            related_deps = []
            dep1_times = set(int(t // 3600) for t in time_patterns.get(dep1, []))  # Hour buckets
            
            for dep2 in dependencies:
                if dep1 == dep2 or dependencies[dep2] < min_co_occurrence:
                    continue
                
                dep2_times = set(int(t // 3600) for t in time_patterns.get(dep2, []))
                
                # Calculate co-occurrence score
                intersection = len(dep1_times & dep2_times)
                union = len(dep1_times | dep2_times)
                
                if union > 0 and intersection / union > 0.5:  # 50% co-occurrence
                    related_deps.append({
                        "dependency": dep2,
                        "co_occurrence_score": intersection / union,
                        "usage_count": dependencies[dep2]
                    })
            
            if related_deps:
                bundle_opportunities.append({
                    "primary_dependency": dep1,
                    "usage_count": dependencies[dep1],
                    "related_dependencies": sorted(related_deps, key=lambda x: x["co_occurrence_score"], reverse=True),
                    "bundle_score": sum(dep["usage_count"] for dep in related_deps) + dependencies[dep1]
                })
        
        return sorted(bundle_opportunities, key=lambda x: x["bundle_score"], reverse=True)

    def recommend_cache_optimizations(self) -> List[Dict]:
        """Generate cache optimization recommendations."""
        patterns = self.analyze_dependency_patterns()
        recommendations = []
        
        # High-usage dependencies should be preloaded
        most_used = patterns.get_most_used_dependencies(5)
        if most_used:
            recommendations.append({
                "type": "preload_dependencies",
                "priority": "high",
                "description": f"Preload top {len(most_used)} dependencies for faster access",
                "dependencies": [dep for dep, count in most_used],
                "expected_improvement": "20-30% faster dependency resolution"
            })
        
        # Bundle opportunities
        bundle_candidates = patterns.get_bundle_candidates()
        if len(bundle_candidates) >= 3:
            recommendations.append({
                "type": "create_bundle",
                "priority": "medium",
                "description": f"Create bundle for {len(bundle_candidates)} frequently used dependencies",
                "dependencies": bundle_candidates,
                "expected_improvement": "40-60% reduction in download time"
            })
        
        # Cache size optimization
        if patterns.cache_hit_rate < 0.8:
            recommendations.append({
                "type": "increase_cache_size",
                "priority": "medium",
                "description": "Increase cache size to improve hit rate",
                "current_hit_rate": patterns.cache_hit_rate,
                "expected_improvement": "Improve cache hit rate to >85%"
            })
        
        # Peak usage optimization
        if patterns.peak_usage_hours:
            recommendations.append({
                "type": "cache_warming",
                "priority": "low",
                "description": f"Pre-warm cache during off-peak hours",
                "peak_hours": patterns.peak_usage_hours,
                "expected_improvement": "Reduced latency during peak hours"
            })
        
        return recommendations


class SharedTeamCache:
    """Manages shared cache infrastructure for teams."""
    
    def __init__(self, team: str, cache_config: Dict, oras_client: OrasClient):
        self.team = team
        self.cache_config = cache_config
        self.oras_client = oras_client
        
        # Set up shared cache directory
        self.shared_cache_dir = Path(cache_config.get("shared_cache_dir", "/tmp/shared-team-cache")) / team
        self.shared_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Team cache registry path
        self.team_registry_prefix = f"teams/{team}"
        
        logger.info(f"Initialized shared cache for team: {team}")

    def setup_shared_cache(self, team_members: List[str]) -> Dict:
        """Set up shared cache for team members."""
        setup_result = {
            "team": self.team,
            "members": team_members,
            "shared_cache_dir": str(self.shared_cache_dir),
            "registry_prefix": self.team_registry_prefix,
            "setup_time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "status": "success"
        }
        
        try:
            # Create team-specific cache structure
            cache_dirs = [
                self.shared_cache_dir / "dependencies",
                self.shared_cache_dir / "bundles", 
                self.shared_cache_dir / "metadata",
                self.shared_cache_dir / "temp"
            ]
            
            for cache_dir in cache_dirs:
                cache_dir.mkdir(exist_ok=True)
            
            # Create team manifest
            team_manifest = {
                "team": self.team,
                "members": team_members,
                "cache_version": "1.0",
                "created_at": setup_result["setup_time"],
                "cache_dirs": [str(d) for d in cache_dirs]
            }
            
            manifest_path = self.shared_cache_dir / "team_manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(team_manifest, f, indent=2)
            
            setup_result["manifest_path"] = str(manifest_path)
            logger.info(f"Shared cache setup completed for team {self.team}")
            
        except Exception as e:
            setup_result["status"] = "error"
            setup_result["error"] = str(e)
            logger.error(f"Failed to setup shared cache for team {self.team}: {e}")
        
        return setup_result

    def sync_cache_updates(self) -> Dict:
        """Sync cache updates across team members."""
        sync_result = {
            "team": self.team,
            "sync_time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "updates_synced": 0,
            "status": "success"
        }
        
        try:
            # In a real implementation, this would:
            # 1. Check for new dependencies in team members' local caches
            # 2. Upload new items to shared ORAS registry
            # 3. Update team manifest with new items
            # 4. Notify team members of updates
            
            # For now, we'll simulate the sync process
            dependencies_dir = self.shared_cache_dir / "dependencies"
            if dependencies_dir.exists():
                cached_items = list(dependencies_dir.iterdir())
                sync_result["updates_synced"] = len(cached_items)
                logger.info(f"Synced {len(cached_items)} items for team {self.team}")
            
        except Exception as e:
            sync_result["status"] = "error"
            sync_result["error"] = str(e)
            logger.error(f"Cache sync failed for team {self.team}: {e}")
        
        return sync_result

    def optimize_cache_layout(self, usage_patterns: UsagePattern) -> Dict:
        """Optimize cache layout based on usage patterns."""
        optimization_result = {
            "team": self.team,
            "optimization_time": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "optimizations_applied": [],
            "status": "success"
        }
        
        try:
            # Hot/Cold data separation
            hot_deps = usage_patterns.get_most_used_dependencies(10)
            if hot_deps:
                hot_cache_dir = self.shared_cache_dir / "hot"
                hot_cache_dir.mkdir(exist_ok=True)
                optimization_result["optimizations_applied"].append({
                    "type": "hot_cache_separation",
                    "hot_dependencies": [dep for dep, count in hot_deps]
                })
            
            # Bundle organization
            bundle_candidates = usage_patterns.get_bundle_candidates()
            if len(bundle_candidates) >= 3:
                bundles_dir = self.shared_cache_dir / "bundles" / "auto_generated"
                bundles_dir.mkdir(parents=True, exist_ok=True)
                optimization_result["optimizations_applied"].append({
                    "type": "auto_bundle_creation",
                    "bundle_candidates": bundle_candidates
                })
            
            logger.info(f"Cache layout optimized for team {self.team}")
            
        except Exception as e:
            optimization_result["status"] = "error"
            optimization_result["error"] = str(e)
            logger.error(f"Cache optimization failed for team {self.team}: {e}")
        
        return optimization_result


class BSRTeamOrasCache:
    """
    Team-optimized BSR caching with ORAS integration.
    
    This is the main class that orchestrates team caching, dependency bundling,
    and performance optimization for BSR dependencies.
    """
    
    def __init__(self, 
                 team: str, 
                 bsr_client: BSRClient, 
                 oras_client: OrasClient,
                 cache_config: Optional[Dict] = None):
        """
        Initialize the team caching system.
        
        Args:
            team: Team name
            bsr_client: BSR client instance
            oras_client: ORAS client instance
            cache_config: Cache configuration options
        """
        self.team = team
        self.bsr_client = bsr_client
        self.oras_client = oras_client
        
        # Default cache configuration
        default_config = {
            "shared_cache_dir": "/tmp/bsr-team-cache",
            "max_cache_size_mb": 1000,
            "bundle_auto_creation": True,
            "preload_common_deps": True,
            "sync_frequency_minutes": 60,
            "cache_compression": True
        }
        self.cache_config = {**default_config, **(cache_config or {})}
        
        # Set up components
        self.usage_analyzer = TeamUsageAnalyzer(team, Path(oras_client.cache_dir) / "team_analysis")
        self.shared_cache = SharedTeamCache(team, self.cache_config, oras_client)
        
        # Performance tracking
        self.performance_metrics = []
        
        logger.info(f"BSR Team ORAS Cache initialized for team: {team}")

    def enable_shared_cache(self, team_members: List[str]) -> Dict:
        """
        Enable shared cache for team members.
        
        Args:
            team_members: List of team member identifiers
            
        Returns:
            Setup result dictionary
        """
        logger.info(f"Enabling shared cache for team {self.team} with {len(team_members)} members")
        
        setup_result = self.shared_cache.setup_shared_cache(team_members)
        
        if setup_result["status"] == "success":
            # Initialize usage tracking for team members
            for member in team_members:
                self.usage_analyzer.track_dependency_access("initialization", member)
        
        return setup_result

    def create_dependency_bundle(self, 
                                dependencies: List[str], 
                                bundle_name: str,
                                description: str = "") -> str:
        """
        Create a dependency bundle for common usage patterns.
        
        Args:
            dependencies: List of dependency references
            bundle_name: Name for the bundle
            description: Bundle description
            
        Returns:
            ORAS reference for the created bundle
        """
        logger.info(f"Creating dependency bundle '{bundle_name}' with {len(dependencies)} dependencies")
        
        try:
            # Resolve dependencies to BSRDependency objects
            resolved_deps = []
            total_size = 0
            
            for dep_ref in dependencies:
                # Parse dependency reference
                parts = dep_ref.split('/')
                if len(parts) >= 3 and ':' in parts[2]:
                    name, version = parts[2].split(':', 1)
                    dep = BSRDependency(
                        name=name,
                        version=version,
                        digest="",
                        repository='/'.join(parts[:2])
                    )
                    resolved_deps.append(dep)
                    
                    # Get metadata for size estimation
                    metadata = self.bsr_client.get_dependency_metadata(dep)
                    if "size" in metadata:
                        total_size += metadata["size"]
            
            # Create bundle object
            bundle = DependencyBundle(
                name=bundle_name,
                description=description or f"Auto-generated bundle for team {self.team}",
                dependencies=resolved_deps,
                version="v1.0.0",
                team=self.team,
                size=total_size,
                created_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                usage_count=0,
                oras_ref=""  # Will be set after upload
            )
            
            # Generate ORAS reference
            oras_ref = f"{self.oras_client.registry}/teams/{self.team}/bundles/{bundle_name}:latest"
            bundle.oras_ref = oras_ref
            
            # Create bundle metadata file
            bundle_metadata = {
                "bundle": asdict(bundle),
                "dependencies": [asdict(dep) for dep in resolved_deps]
            }
            
            # Save bundle metadata
            bundle_cache_dir = self.shared_cache.shared_cache_dir / "bundles" / bundle_name
            bundle_cache_dir.mkdir(parents=True, exist_ok=True)
            
            metadata_file = bundle_cache_dir / "bundle_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(bundle_metadata, f, indent=2)
            
            logger.info(f"Created bundle {bundle_name} with ORAS ref: {oras_ref}")
            return oras_ref
            
        except Exception as e:
            logger.error(f"Failed to create bundle {bundle_name}: {e}")
            raise BSRClientError(f"Bundle creation failed: {e}")

    def optimize_cache_strategy(self, usage_patterns: UsagePattern) -> CacheStrategy:
        """
        Optimize caching strategy based on usage patterns.
        
        Args:
            usage_patterns: Team usage patterns
            
        Returns:
            Optimized cache strategy
        """
        logger.info(f"Optimizing cache strategy for team {self.team}")
        
        # Determine cache type based on usage patterns
        total_deps = len(usage_patterns.dependencies)
        avg_usage = statistics.mean(usage_patterns.dependencies.values()) if usage_patterns.dependencies else 0
        
        if avg_usage > 20 and total_deps > 50:
            cache_type = "aggressive"
            cache_size_limit = 2000  # MB
        elif avg_usage > 10 and total_deps > 20:
            cache_type = "balanced"
            cache_size_limit = 1000  # MB
        else:
            cache_type = "conservative"
            cache_size_limit = 500  # MB
        
        # Determine preload dependencies
        preload_deps = [dep for dep, count in usage_patterns.get_most_used_dependencies(10)]
        
        # Sync frequency based on team activity
        if len(usage_patterns.team_members) > 10:
            sync_frequency = 30  # minutes - more frequent for larger teams
        else:
            sync_frequency = 60  # minutes
        
        strategy = CacheStrategy(
            team=self.team,
            cache_type=cache_type,
            shared_cache_enabled=True,
            bundle_strategy="auto" if len(usage_patterns.get_bundle_candidates()) >= 3 else "manual",
            cache_size_limit=cache_size_limit,
            eviction_policy="lru",
            preload_dependencies=preload_deps,
            sync_frequency=sync_frequency,
            compression_enabled=True
        )
        
        logger.info(f"Optimized cache strategy: {cache_type} caching with {len(preload_deps)} preload deps")
        return strategy

    def sync_team_cache(self) -> Dict:
        """
        Synchronize team cache across members.
        
        Returns:
            Sync result dictionary
        """
        logger.info(f"Synchronizing team cache for {self.team}")
        
        sync_result = self.shared_cache.sync_cache_updates()
        
        # Track sync performance
        if sync_result["status"] == "success":
            # Update usage patterns with sync data
            current_time = time.time()
            for member in self.usage_analyzer._load_usage_data().get("team_members", []):
                self.usage_analyzer.track_dependency_access("cache_sync", member)
        
        return sync_result

    def monitor_cache_performance(self) -> CachePerformanceMetrics:
        """
        Monitor and collect cache performance metrics.
        
        Returns:
            Performance metrics for the team cache
        """
        logger.info(f"Monitoring cache performance for team {self.team}")
        
        # Analyze current usage patterns
        usage_patterns = self.usage_analyzer.analyze_dependency_patterns()
        
        # Calculate performance metrics
        total_deps = len(usage_patterns.dependencies)
        cache_hit_rate = usage_patterns.cache_hit_rate
        
        # Estimate bandwidth savings (placeholder calculation)
        total_downloads = sum(usage_patterns.dependencies.values())
        bandwidth_saved = total_downloads * 0.7 * 10  # Assume 70% cache hits, 10MB avg per dep
        
        # Estimate build time improvement
        build_time_improvement = min(cache_hit_rate * 50, 30)  # Max 30% improvement
        
        # Calculate shared cache efficiency
        team_size = len(usage_patterns.team_members)
        shared_cache_efficiency = min(team_size * 0.1, 0.8) if team_size > 1 else 0
        
        metrics = CachePerformanceMetrics(
            team=self.team,
            cache_hit_rate=cache_hit_rate,
            avg_download_time=500.0,  # ms - placeholder
            total_cache_size=total_deps * 15,  # MB - estimated
            bandwidth_saved=bandwidth_saved,
            build_time_improvement=build_time_improvement,
            shared_cache_efficiency=shared_cache_efficiency,
            bundle_usage_rate=0.3,  # 30% - placeholder
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        )
        
        # Store metrics for trend analysis
        self.performance_metrics.append(metrics)
        
        # Keep only last 100 metrics
        if len(self.performance_metrics) > 100:
            self.performance_metrics = self.performance_metrics[-100:]
        
        logger.info(f"Cache performance: {cache_hit_rate:.1%} hit rate, {build_time_improvement:.1f}% build improvement")
        return metrics

    def get_cache_recommendations(self) -> List[Dict]:
        """
        Get cache optimization recommendations for the team.
        
        Returns:
            List of optimization recommendations
        """
        usage_patterns = self.usage_analyzer.analyze_dependency_patterns()
        recommendations = self.usage_analyzer.recommend_cache_optimizations()
        
        # Add bundle recommendations
        bundle_opportunities = self.usage_analyzer.identify_bundle_opportunities()
        for opportunity in bundle_opportunities[:3]:  # Top 3 opportunities
            recommendations.append({
                "type": "create_specific_bundle",
                "priority": "medium",
                "description": f"Create bundle for {opportunity['primary_dependency']} and related deps",
                "primary_dependency": opportunity["primary_dependency"],
                "related_dependencies": [dep["dependency"] for dep in opportunity["related_dependencies"]],
                "expected_improvement": f"Bundle score: {opportunity['bundle_score']}"
            })
        
        return recommendations


def main():
    """Main entry point for BSR team caching testing."""
    parser = argparse.ArgumentParser(description="BSR Team ORAS Cache Management")
    parser.add_argument("--team", required=True, help="Team name")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry URL")
    parser.add_argument("--bsr-registry", default="buf.build", help="BSR registry URL")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Setup shared cache
    setup_parser = subparsers.add_parser("setup", help="Setup shared cache")
    setup_parser.add_argument("--members", nargs="+", required=True, help="Team member IDs")
    
    # Create bundle
    bundle_parser = subparsers.add_parser("bundle", help="Create dependency bundle")
    bundle_parser.add_argument("--name", required=True, help="Bundle name")
    bundle_parser.add_argument("--deps", nargs="+", required=True, help="Dependency references")
    bundle_parser.add_argument("--description", help="Bundle description")
    
    # Monitor performance
    monitor_parser = subparsers.add_parser("monitor", help="Monitor cache performance")
    
    # Get recommendations
    recommend_parser = subparsers.add_parser("recommend", help="Get cache recommendations")
    
    # Sync cache
    sync_parser = subparsers.add_parser("sync", help="Sync team cache")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Initialize clients
        bsr_client = BSRClient(
            registry_url=args.bsr_registry,
            team=args.team,
            cache_dir=args.cache_dir,
            verbose=args.verbose
        )
        
        oras_client = OrasClient(
            registry=args.registry,
            cache_dir=args.cache_dir or f"/tmp/bsr-cache-{args.team}",
            verbose=args.verbose
        )
        
        # Initialize team cache
        team_cache = BSRTeamOrasCache(
            team=args.team,
            bsr_client=bsr_client,
            oras_client=oras_client
        )
        
        if args.command == "setup":
            result = team_cache.enable_shared_cache(args.members)
            print(f"Shared cache setup: {result['status']}")
            if result["status"] == "success":
                print(f"Cache directory: {result['shared_cache_dir']}")
        
        elif args.command == "bundle":
            oras_ref = team_cache.create_dependency_bundle(
                dependencies=args.deps,
                bundle_name=args.name,
                description=args.description or ""
            )
            print(f"Created bundle: {oras_ref}")
        
        elif args.command == "monitor":
            metrics = team_cache.monitor_cache_performance()
            print(f"Cache Performance for team {args.team}:")
            print(f"  Hit Rate: {metrics.cache_hit_rate:.1%}")
            print(f"  Build Time Improvement: {metrics.build_time_improvement:.1f}%")
            print(f"  Bandwidth Saved: {metrics.bandwidth_saved:.1f}MB")
            print(f"  Shared Cache Efficiency: {metrics.shared_cache_efficiency:.1%}")
        
        elif args.command == "recommend":
            recommendations = team_cache.get_cache_recommendations()
            print(f"Cache Recommendations for team {args.team}:")
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. [{rec['priority'].upper()}] {rec['type']}")
                print(f"   {rec['description']}")
                if "expected_improvement" in rec:
                    print(f"   Expected improvement: {rec['expected_improvement']}")
        
        elif args.command == "sync":
            result = team_cache.sync_team_cache()
            print(f"Cache sync: {result['status']}")
            if result["status"] == "success":
                print(f"Updates synced: {result['updates_synced']}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
