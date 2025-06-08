"""
Buck2 rules for BSR team caching optimization.

This module provides Buck2 rules that integrate with the BSR team caching
system for optimized dependency management and team collaboration.
"""

load("//rules/private:providers.bzl", "ProtoInfo")
load("//rules/private:utils.bzl", "get_platform_string")

def _bsr_team_cache_config_impl(ctx):
    """Implementation for bsr_team_cache_config rule."""
    
    # Create team cache configuration
    cache_config = {
        "team": ctx.attr.team,
        "shared_cache": ctx.attr.shared_cache,
        "team_members": ctx.attr.team_members,
        "cache_strategy": ctx.attr.cache_strategy,
        "bundle_auto_creation": ctx.attr.bundle_auto_creation,
        "preload_dependencies": ctx.attr.preload_dependencies,
        "sync_frequency_minutes": ctx.attr.sync_frequency_minutes,
        "max_cache_size_mb": ctx.attr.max_cache_size_mb,
    }
    
    # Write configuration to file
    config_file = ctx.actions.declare_output("team_cache_config.json")
    ctx.actions.write(config_file, json.encode(cache_config))
    
    return [
        DefaultInfo(
            default_output = config_file,
            sub_targets = {
                "config": [DefaultInfo(default_output = config_file)],
            },
        ),
    ]

bsr_team_cache_config = rule(
    impl = _bsr_team_cache_config_impl,
    attrs = {
        "team": attrs.string(
            doc = "Team name for cache configuration",
            mandatory = True,
        ),
        "shared_cache": attrs.bool(
            doc = "Enable shared cache for team",
            default = True,
        ),
        "team_members": attrs.list(
            attrs.string(),
            doc = "List of team member identifiers",
            default = [],
        ),
        "cache_strategy": attrs.enum(
            ["aggressive", "balanced", "conservative"],
            doc = "Caching strategy for the team",
            default = "balanced",
        ),
        "bundle_auto_creation": attrs.bool(
            doc = "Enable automatic bundle creation",
            default = True,
        ),
        "preload_dependencies": attrs.list(
            attrs.string(),
            doc = "Dependencies to preload in cache",
            default = [],
        ),
        "sync_frequency_minutes": attrs.int(
            doc = "Cache sync frequency in minutes",
            default = 60,
        ),
        "max_cache_size_mb": attrs.int(
            doc = "Maximum cache size in MB",
            default = 1000,
        ),
    },
    doc = "Configure BSR team caching for a development team",
)

def _dependency_bundle_impl(ctx):
    """Implementation for dependency_bundle rule."""
    
    # Create bundle specification
    bundle_spec = {
        "name": ctx.attr.bundle_name,
        "description": ctx.attr.description,
        "dependencies": ctx.attr.dependencies,
        "team": ctx.attr.team,
        "version": ctx.attr.version,
        "auto_update": ctx.attr.auto_update,
    }
    
    # Generate bundle creation script
    bundle_script = ctx.actions.declare_output("create_bundle.py")
    script_content = _generate_bundle_creation_script(bundle_spec)
    ctx.actions.write(bundle_script, script_content)
    
    # Create bundle metadata
    bundle_metadata = ctx.actions.declare_output("bundle_metadata.json")
    ctx.actions.write(bundle_metadata, json.encode(bundle_spec))
    
    return [
        DefaultInfo(
            default_output = bundle_script,
            sub_targets = {
                "metadata": [DefaultInfo(default_output = bundle_metadata)],
                "script": [DefaultInfo(default_output = bundle_script)],
            },
        ),
    ]

dependency_bundle = rule(
    impl = _dependency_bundle_impl,
    attrs = {
        "bundle_name": attrs.string(
            doc = "Name for the dependency bundle",
            mandatory = True,
        ),
        "description": attrs.string(
            doc = "Description of the bundle",
            default = "",
        ),
        "dependencies": attrs.list(
            attrs.string(),
            doc = "List of BSR dependency references",
            mandatory = True,
        ),
        "team": attrs.string(
            doc = "Team name for the bundle",
            mandatory = True,
        ),
        "version": attrs.string(
            doc = "Bundle version",
            default = "v1.0.0",
        ),
        "auto_update": attrs.bool(
            doc = "Enable automatic bundle updates",
            default = False,
        ),
    },
    doc = "Create a dependency bundle for team use",
)

def _cache_performance_monitor_impl(ctx):
    """Implementation for cache_performance_monitor rule."""
    
    # Create monitoring configuration
    monitor_config = {
        "team": ctx.attr.team,
        "metrics": ctx.attr.metrics,
        "reporting_frequency": ctx.attr.reporting_frequency,
        "alert_thresholds": {
            "cache_hit_rate_min": ctx.attr.cache_hit_rate_threshold,
            "build_time_regression_max": ctx.attr.build_time_regression_threshold,
        },
        "dashboard_enabled": ctx.attr.dashboard_enabled,
    }
    
    # Generate monitoring script
    monitor_script = ctx.actions.declare_output("monitor_cache.py")
    script_content = _generate_monitoring_script(monitor_config)
    ctx.actions.write(monitor_script, script_content)
    
    # Create configuration file
    config_file = ctx.actions.declare_output("monitor_config.json")
    ctx.actions.write(config_file, json.encode(monitor_config))
    
    return [
        DefaultInfo(
            default_output = monitor_script,
            sub_targets = {
                "config": [DefaultInfo(default_output = config_file)],
                "script": [DefaultInfo(default_output = monitor_script)],
            },
        ),
    ]

cache_performance_monitor = rule(
    impl = _cache_performance_monitor_impl,
    attrs = {
        "team": attrs.string(
            doc = "Team name to monitor",
            mandatory = True,
        ),
        "metrics": attrs.list(
            attrs.enum(["hit_rate", "download_time", "storage_usage", "build_improvement"]),
            doc = "Metrics to monitor",
            default = ["hit_rate", "download_time", "build_improvement"],
        ),
        "reporting_frequency": attrs.enum(
            ["hourly", "daily", "weekly"],
            doc = "How often to generate reports",
            default = "daily",
        ),
        "cache_hit_rate_threshold": attrs.float(
            doc = "Minimum cache hit rate threshold (0.0-1.0)",
            default = 0.85,
        ),
        "build_time_regression_threshold": attrs.float(
            doc = "Maximum build time regression threshold (0.0-1.0)",
            default = 0.10,
        ),
        "dashboard_enabled": attrs.bool(
            doc = "Enable performance dashboard",
            default = True,
        ),
    },
    doc = "Monitor team cache performance and generate reports",
)

def _generate_bundle_creation_script(bundle_spec):
    """Generate Python script for creating dependency bundles."""
    return '''#!/usr/bin/env python3
"""
Generated bundle creation script for {bundle_name}.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))

from bsr_team_oras_cache import BSRTeamOrasCache
from bsr_client import BSRClient
from oras_client import OrasClient

def main():
    """Create dependency bundle."""
    
    # Initialize clients
    bsr_client = BSRClient(team="{team}")
    oras_client = OrasClient(registry="oras.birb.homes", cache_dir="/tmp/bsr-cache-{team}")
    
    # Initialize team cache
    team_cache = BSRTeamOrasCache(
        team="{team}",
        bsr_client=bsr_client,
        oras_client=oras_client
    )
    
    # Create bundle
    dependencies = {dependencies}
    oras_ref = team_cache.create_dependency_bundle(
        dependencies=dependencies,
        bundle_name="{bundle_name}",
        description="{description}"
    )
    
    print(f"Created bundle: {{oras_ref}}")
    return 0

if __name__ == "__main__":
    exit(main())
'''.format(
        bundle_name = bundle_spec["name"],
        team = bundle_spec["team"],
        dependencies = bundle_spec["dependencies"],
        description = bundle_spec["description"],
    )

def _generate_monitoring_script(monitor_config):
    """Generate Python script for cache monitoring."""
    return '''#!/usr/bin/env python3
"""
Generated cache monitoring script for team {team}.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools"))

from bsr_team_oras_cache import BSRTeamOrasCache
from bsr_client import BSRClient
from oras_client import OrasClient

def main():
    """Monitor cache performance."""
    
    # Initialize clients
    bsr_client = BSRClient(team="{team}")
    oras_client = OrasClient(registry="oras.birb.homes", cache_dir="/tmp/bsr-cache-{team}")
    
    # Initialize team cache
    team_cache = BSRTeamOrasCache(
        team="{team}",
        bsr_client=bsr_client,
        oras_client=oras_client
    )
    
    # Monitor performance
    metrics = team_cache.monitor_cache_performance()
    
    print(f"Cache Performance for team {team}:")
    print(f"  Hit Rate: {{metrics.cache_hit_rate:.1%}}")
    print(f"  Build Time Improvement: {{metrics.build_time_improvement:.1f}}%")
    print(f"  Bandwidth Saved: {{metrics.bandwidth_saved:.1f}}MB")
    print(f"  Shared Cache Efficiency: {{metrics.shared_cache_efficiency:.1%}}")
    
    # Check thresholds
    if metrics.cache_hit_rate < {cache_hit_rate_threshold}:
        print(f"⚠️  Cache hit rate below threshold!")
        return 1
    
    print("✅ Cache performance within acceptable range")
    return 0

if __name__ == "__main__":
    exit(main())
'''.format(
        team = monitor_config["team"],
        cache_hit_rate_threshold = monitor_config["alert_thresholds"]["cache_hit_rate_min"],
    )

# Helper function for team cache integration in proto rules
def integrate_team_cache(ctx, deps):
    """
    Integrate team cache with proto rule dependencies.
    
    Args:
        ctx: Rule context
        deps: List of dependency targets
        
    Returns:
        Tuple of (cache_info, optimized_deps)
    """
    
    # Extract team information from context if available
    team = getattr(ctx.attr, "team", None)
    if not team:
        # No team specified, use regular dependencies
        return None, deps
    
    # Check for team cache configuration
    team_cache_config = None
    for dep in deps:
        if hasattr(dep, "team_cache_config"):
            team_cache_config = dep.team_cache_config
            break
    
    if not team_cache_config:
        # No team cache config found
        return None, deps
    
    # Create cache info
    cache_info = struct(
        team = team,
        config = team_cache_config,
        enabled = True,
    )
    
    # TODO: In a real implementation, this would:
    # 1. Check if dependencies are available in team cache
    # 2. Use cached versions if available
    # 3. Track usage for optimization
    # 4. Update team usage patterns
    
    return cache_info, deps

# Macro for easy team cache setup
def setup_team_cache(
    name,
    team,
    members = [],
    shared_cache = True,
    cache_strategy = "balanced",
    bundle_dependencies = [],
    monitor_performance = True):
    """
    Set up comprehensive team caching for a development team.
    
    Args:
        name: Name for the cache setup
        team: Team name
        members: List of team member identifiers
        shared_cache: Enable shared cache
        cache_strategy: Caching strategy (aggressive/balanced/conservative)
        bundle_dependencies: Dependencies to bundle together
        monitor_performance: Enable performance monitoring
    """
    
    # Create team cache configuration
    bsr_team_cache_config(
        name = name + "_config",
        team = team,
        team_members = members,
        shared_cache = shared_cache,
        cache_strategy = cache_strategy,
    )
    
    # Create dependency bundle if specified
    if bundle_dependencies:
        dependency_bundle(
            name = name + "_bundle",
            bundle_name = team + "_common",
            dependencies = bundle_dependencies,
            team = team,
            description = "Common dependencies for " + team,
        )
    
    # Set up performance monitoring
    if monitor_performance:
        cache_performance_monitor(
            name = name + "_monitor",
            team = team,
            metrics = ["hit_rate", "download_time", "build_improvement"],
            reporting_frequency = "daily",
        )

# Example of enhanced proto_library rule with team caching
def team_proto_library(
    name,
    srcs,
    deps = [],
    team = None,
    use_team_cache = True,
    **kwargs):
    """
    Enhanced proto_library rule with team caching support.
    
    Args:
        name: Target name
        srcs: Proto source files
        deps: Dependencies
        team: Team name for caching
        use_team_cache: Enable team cache integration
        **kwargs: Additional arguments passed to proto_library
    """
    
    # Import the base proto_library rule
    load("//rules:proto.bzl", "proto_library")
    
    # Add team cache integration attributes if specified
    if team and use_team_cache:
        kwargs["team"] = team
        kwargs["use_team_cache"] = use_team_cache
    
    # Call the base proto_library rule
    proto_library(
        name = name,
        srcs = srcs,
        deps = deps,
        **kwargs
    )
