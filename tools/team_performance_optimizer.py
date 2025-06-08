#!/usr/bin/env python3
"""
Team Performance Optimizer for Team Collaboration.

This module provides team-specific performance optimization capabilities,
analyzing usage patterns and providing targeted improvements for build
performance, caching strategies, and workflow optimization.
"""

import argparse
import json
import os
import time
import statistics
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials
from .bsr_teams import BSRTeamManager, Team
from .performance_monitor import PerformanceMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class UsagePattern:
    """Represents team usage patterns for protobuf schemas."""
    team_name: str
    schema_targets: List[str] = field(default_factory=list)
    build_frequency: Dict[str, int] = field(default_factory=dict)  # target -> builds per day
    cache_hit_rates: Dict[str, float] = field(default_factory=dict)  # target -> hit rate
    build_times: Dict[str, List[float]] = field(default_factory=dict)  # target -> [build times]
    dependency_patterns: Dict[str, List[str]] = field(default_factory=dict)  # target -> [dependencies]
    team_size: int = 0
    active_developers: int = 0
    primary_languages: List[str] = field(default_factory=list)
    workflow_characteristics: Dict[str, Any] = field(default_factory=dict)
    analysis_period: str = "7d"
    last_analyzed: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))


@dataclass
class CacheStrategy:
    """Represents an optimized caching strategy for a team."""
    team_name: str
    strategy_type: str  # "aggressive", "balanced", "conservative"
    cache_policies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    prefetch_targets: List[str] = field(default_factory=list)
    eviction_rules: Dict[str, Any] = field(default_factory=dict)
    shared_cache_config: Dict[str, Any] = field(default_factory=dict)
    estimated_improvement: Dict[str, str] = field(default_factory=dict)  # metric -> improvement
    implementation_steps: List[str] = field(default_factory=list)
    monitoring_metrics: List[str] = field(default_factory=list)


@dataclass
class WorkflowImprovement:
    """Represents a workflow improvement recommendation."""
    improvement_type: str  # "build_optimization", "dependency_management", "automation"
    title: str
    description: str
    priority: str  # "low", "medium", "high", "critical"
    estimated_impact: str  # "low", "medium", "high"
    implementation_effort: str  # "minimal", "low", "medium", "high"
    prerequisites: List[str] = field(default_factory=list)
    implementation_steps: List[str] = field(default_factory=list)
    success_metrics: List[str] = field(default_factory=list)
    estimated_time_savings: Optional[str] = None


@dataclass
class TeamOptimizationReport:
    """Comprehensive optimization report for a team."""
    team_name: str
    analysis_period: str
    current_performance: Dict[str, Any] = field(default_factory=dict)
    usage_patterns: Optional[UsagePattern] = None
    cache_strategy: Optional[CacheStrategy] = None
    workflow_improvements: List[WorkflowImprovement] = field(default_factory=list)
    performance_baseline: Dict[str, float] = field(default_factory=dict)
    projected_improvements: Dict[str, str] = field(default_factory=dict)
    implementation_roadmap: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))


class PerformanceOptimizationError(Exception):
    """Performance optimization operation failed."""
    pass


class TeamPerformanceOptimizer:
    """
    Team-specific performance optimization system.
    
    Analyzes team usage patterns and provides targeted optimization
    recommendations for build performance, caching, and workflows.
    """
    
    def __init__(self,
                 storage_dir: Union[str, Path] = None,
                 team_manager: Optional[BSRTeamManager] = None,
                 performance_monitor: Optional[PerformanceMonitor] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 verbose: bool = False):
        """
        Initialize Team Performance Optimizer.
        
        Args:
            storage_dir: Directory for optimization data storage
            team_manager: BSR team manager instance
            performance_monitor: Performance monitoring instance
            bsr_authenticator: BSR authentication instance
            verbose: Enable verbose logging
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'team-optimization'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Storage files
        self.usage_patterns_file = self.storage_dir / "usage_patterns.json"
        self.cache_strategies_file = self.storage_dir / "cache_strategies.json"
        self.optimization_reports_file = self.storage_dir / "optimization_reports.json"
        self.performance_baselines_file = self.storage_dir / "performance_baselines.json"
        
        # Dependencies
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        self.performance_monitor = performance_monitor or PerformanceMonitor(verbose=verbose)
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Initialize storage
        self._init_storage()
        
        logger.info(f"Team Performance Optimizer initialized")

    def _init_storage(self) -> None:
        """Initialize storage files."""
        for file_path in [self.usage_patterns_file, self.cache_strategies_file,
                         self.optimization_reports_file, self.performance_baselines_file]:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump({}, f)

    def analyze_team_usage_patterns(self, 
                                  team_name: str,
                                  analysis_period: str = "7d") -> UsagePattern:
        """
        Analyze team usage patterns for protobuf schemas.
        
        Args:
            team_name: Name of the team to analyze
            analysis_period: Period for analysis ("1d", "7d", "30d")
            
        Returns:
            UsagePattern with comprehensive team analysis
        """
        # Get team information
        team_info = self.team_manager.get_team_info(team_name)
        if not team_info:
            raise PerformanceOptimizationError(f"Team {team_name} not found")
        
        # Initialize usage pattern
        usage_pattern = UsagePattern(
            team_name=team_name,
            analysis_period=analysis_period,
            team_size=team_info['member_count']
        )
        
        # Analyze team repositories and schema targets
        schema_targets = []
        for repo_name, repo_config in team_info.get('repositories', {}).items():
            # In a real implementation, this would scan the repository for proto targets
            schema_targets.extend(self._discover_schema_targets(repo_name))
        
        usage_pattern.schema_targets = schema_targets
        
        # Analyze build patterns
        usage_pattern.build_frequency = self._analyze_build_frequency(
            team_name, schema_targets, analysis_period
        )
        
        # Analyze cache performance
        usage_pattern.cache_hit_rates = self._analyze_cache_performance(
            team_name, schema_targets, analysis_period
        )
        
        # Analyze build times
        usage_pattern.build_times = self._analyze_build_times(
            team_name, schema_targets, analysis_period
        )
        
        # Analyze dependency patterns
        usage_pattern.dependency_patterns = self._analyze_dependency_patterns(
            team_name, schema_targets
        )
        
        # Determine primary languages
        usage_pattern.primary_languages = self._analyze_primary_languages(team_info)
        
        # Analyze workflow characteristics
        usage_pattern.workflow_characteristics = self._analyze_workflow_characteristics(
            team_name, team_info
        )
        
        # Estimate active developers
        usage_pattern.active_developers = self._estimate_active_developers(
            team_name, analysis_period
        )
        
        # Save usage pattern
        self._save_usage_pattern(team_name, usage_pattern)
        
        logger.info(f"Analyzed usage patterns for team {team_name}")
        
        return usage_pattern

    def optimize_caching_strategy(self,
                                team_name: str,
                                usage_pattern: Optional[UsagePattern] = None) -> CacheStrategy:
        """
        Generate optimized caching strategy for a team.
        
        Args:
            team_name: Name of the team
            usage_pattern: Optional pre-analyzed usage pattern
            
        Returns:
            Optimized CacheStrategy for the team
        """
        if not usage_pattern:
            usage_pattern = self.analyze_team_usage_patterns(team_name)
        
        # Determine optimal strategy type based on team characteristics
        strategy_type = self._determine_cache_strategy_type(usage_pattern)
        
        # Create cache strategy
        cache_strategy = CacheStrategy(
            team_name=team_name,
            strategy_type=strategy_type
        )
        
        # Configure cache policies
        cache_strategy.cache_policies = self._generate_cache_policies(
            usage_pattern, strategy_type
        )
        
        # Determine prefetch targets
        cache_strategy.prefetch_targets = self._determine_prefetch_targets(usage_pattern)
        
        # Configure eviction rules
        cache_strategy.eviction_rules = self._generate_eviction_rules(
            usage_pattern, strategy_type
        )
        
        # Configure shared cache settings
        cache_strategy.shared_cache_config = self._generate_shared_cache_config(
            usage_pattern, strategy_type
        )
        
        # Estimate improvements
        cache_strategy.estimated_improvement = self._estimate_cache_improvements(
            usage_pattern, cache_strategy
        )
        
        # Generate implementation steps
        cache_strategy.implementation_steps = self._generate_cache_implementation_steps(
            cache_strategy
        )
        
        # Define monitoring metrics
        cache_strategy.monitoring_metrics = self._define_cache_monitoring_metrics()
        
        # Save cache strategy
        self._save_cache_strategy(team_name, cache_strategy)
        
        logger.info(f"Generated cache strategy for team {team_name}: {strategy_type}")
        
        return cache_strategy

    def recommend_workflow_improvements(self,
                                      team_name: str,
                                      usage_pattern: Optional[UsagePattern] = None) -> List[WorkflowImprovement]:
        """
        Generate workflow improvement recommendations for a team.
        
        Args:
            team_name: Name of the team
            usage_pattern: Optional pre-analyzed usage pattern
            
        Returns:
            List of WorkflowImprovement recommendations
        """
        if not usage_pattern:
            usage_pattern = self.analyze_team_usage_patterns(team_name)
        
        improvements = []
        
        # Build optimization improvements
        build_improvements = self._analyze_build_optimizations(usage_pattern)
        improvements.extend(build_improvements)
        
        # Dependency management improvements
        dependency_improvements = self._analyze_dependency_optimizations(usage_pattern)
        improvements.extend(dependency_improvements)
        
        # Automation improvements
        automation_improvements = self._analyze_automation_opportunities(usage_pattern)
        improvements.extend(automation_improvements)
        
        # Workflow-specific improvements
        workflow_improvements = self._analyze_workflow_specific_optimizations(usage_pattern)
        improvements.extend(workflow_improvements)
        
        # Sort by priority and impact
        improvements.sort(key=lambda x: (
            self._priority_score(x.priority),
            self._impact_score(x.estimated_impact)
        ), reverse=True)
        
        logger.info(f"Generated {len(improvements)} workflow improvements for team {team_name}")
        
        return improvements

    def generate_optimization_report(self,
                                   team_name: str,
                                   analysis_period: str = "7d") -> TeamOptimizationReport:
        """
        Generate comprehensive optimization report for a team.
        
        Args:
            team_name: Name of the team
            analysis_period: Period for analysis
            
        Returns:
            Comprehensive TeamOptimizationReport
        """
        # Analyze usage patterns
        usage_patterns = self.analyze_team_usage_patterns(team_name, analysis_period)
        
        # Generate cache strategy
        cache_strategy = self.optimize_caching_strategy(team_name, usage_patterns)
        
        # Get workflow improvements
        workflow_improvements = self.recommend_workflow_improvements(team_name, usage_patterns)
        
        # Get current performance baseline
        performance_baseline = self._get_performance_baseline(team_name)
        
        # Create optimization report
        report = TeamOptimizationReport(
            team_name=team_name,
            analysis_period=analysis_period,
            usage_patterns=usage_patterns,
            cache_strategy=cache_strategy,
            workflow_improvements=workflow_improvements,
            performance_baseline=performance_baseline
        )
        
        # Analyze current performance
        report.current_performance = self._analyze_current_performance(usage_patterns)
        
        # Project improvements
        report.projected_improvements = self._project_improvements(
            usage_patterns, cache_strategy, workflow_improvements
        )
        
        # Generate implementation roadmap
        report.implementation_roadmap = self._generate_implementation_roadmap(
            cache_strategy, workflow_improvements
        )
        
        # Save optimization report
        self._save_optimization_report(team_name, report)
        
        logger.info(f"Generated optimization report for team {team_name}")
        
        return report

    # Helper methods
    
    def _discover_schema_targets(self, repository: str) -> List[str]:
        """Discover schema targets in a repository."""
        # In a real implementation, this would scan the repository
        # For now, return some example targets
        return [
            f"//{repository}:user_proto",
            f"//{repository}:api_proto",
            f"//{repository}:service_proto"
        ]

    def _analyze_build_frequency(self,
                                team_name: str,
                                schema_targets: List[str],
                                analysis_period: str) -> Dict[str, int]:
        """Analyze build frequency for schema targets."""
        # In a real implementation, this would query build logs
        # For now, generate realistic patterns
        frequency = {}
        for target in schema_targets:
            # Simulate different usage patterns
            if "api" in target:
                frequency[target] = 50  # High frequency API schemas
            elif "service" in target:
                frequency[target] = 20  # Medium frequency service schemas
            else:
                frequency[target] = 10  # Low frequency schemas
        
        return frequency

    def _analyze_cache_performance(self,
                                 team_name: str,
                                 schema_targets: List[str],
                                 analysis_period: str) -> Dict[str, float]:
        """Analyze cache hit rates for schema targets."""
        hit_rates = {}
        for target in schema_targets:
            # Simulate cache performance based on build frequency
            if "api" in target:
                hit_rates[target] = 0.75  # Good cache performance for frequently used
            elif "service" in target:
                hit_rates[target] = 0.60  # Medium cache performance
            else:
                hit_rates[target] = 0.40  # Poor cache performance for infrequent
        
        return hit_rates

    def _analyze_build_times(self,
                           team_name: str,
                           schema_targets: List[str],
                           analysis_period: str) -> Dict[str, List[float]]:
        """Analyze build times for schema targets."""
        build_times = {}
        for target in schema_targets:
            # Simulate build time patterns
            if "api" in target:
                # Consistent fast builds
                build_times[target] = [2.1, 2.3, 2.0, 2.2, 2.1, 2.4, 2.0]
            elif "service" in target:
                # Variable medium builds
                build_times[target] = [5.2, 4.8, 5.5, 5.0, 5.3, 4.9, 5.1]
            else:
                # Slow, variable builds
                build_times[target] = [12.1, 11.8, 13.2, 12.5, 11.9, 12.8, 12.3]
        
        return build_times

    def _analyze_dependency_patterns(self,
                                   team_name: str,
                                   schema_targets: List[str]) -> Dict[str, List[str]]:
        """Analyze dependency patterns for schema targets."""
        dependencies = {}
        for target in schema_targets:
            if "api" in target:
                dependencies[target] = ["//common:base_proto"]
            elif "service" in target:
                dependencies[target] = ["//common:base_proto", f"//{team_name}:api_proto"]
            else:
                dependencies[target] = []
        
        return dependencies

    def _analyze_primary_languages(self, team_info: Dict[str, Any]) -> List[str]:
        """Analyze primary programming languages used by team."""
        # In a real implementation, this would analyze repository languages
        # For now, return common combinations
        return ["python", "go", "typescript"]

    def _analyze_workflow_characteristics(self,
                                        team_name: str,
                                        team_info: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze team workflow characteristics."""
        return {
            "ci_cd_frequency": "high",  # multiple times per day
            "testing_strategy": "comprehensive",
            "deployment_pattern": "continuous",
            "code_review_practice": "mandatory",
            "branch_strategy": "feature_branches"
        }

    def _estimate_active_developers(self, team_name: str, analysis_period: str) -> int:
        """Estimate number of active developers."""
        team_info = self.team_manager.get_team_info(team_name)
        if team_info:
            # Assume 80% of team members are active in a given period
            return int(team_info['member_count'] * 0.8)
        return 1

    def _determine_cache_strategy_type(self, usage_pattern: UsagePattern) -> str:
        """Determine optimal cache strategy type."""
        # Analyze usage characteristics
        total_builds = sum(usage_pattern.build_frequency.values())
        avg_cache_hit_rate = statistics.mean(usage_pattern.cache_hit_rates.values()) if usage_pattern.cache_hit_rates else 0.5
        
        if total_builds > 100 and avg_cache_hit_rate < 0.6:
            return "aggressive"  # High usage, low hit rate
        elif total_builds > 50 or usage_pattern.active_developers > 5:
            return "balanced"  # Medium usage or large team
        else:
            return "conservative"  # Low usage or small team

    def _generate_cache_policies(self,
                               usage_pattern: UsagePattern,
                               strategy_type: str) -> Dict[str, Dict[str, Any]]:
        """Generate cache policies based on usage patterns."""
        policies = {}
        
        if strategy_type == "aggressive":
            policies["default"] = {
                "ttl": "24h",
                "max_size": "10GB",
                "compression": True,
                "remote_cache": True
            }
            policies["frequent_targets"] = {
                "ttl": "48h",
                "priority": "high",
                "preload": True
            }
        elif strategy_type == "balanced":
            policies["default"] = {
                "ttl": "12h",
                "max_size": "5GB",
                "compression": True,
                "remote_cache": True
            }
        else:  # conservative
            policies["default"] = {
                "ttl": "6h",
                "max_size": "2GB",
                "compression": False,
                "remote_cache": False
            }
        
        return policies

    def _determine_prefetch_targets(self, usage_pattern: UsagePattern) -> List[str]:
        """Determine targets that should be prefetched."""
        # Sort targets by build frequency and return top frequently used
        sorted_targets = sorted(
            usage_pattern.build_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Prefetch top 3 most frequently used targets
        return [target for target, _ in sorted_targets[:3]]

    def _generate_eviction_rules(self,
                               usage_pattern: UsagePattern,
                               strategy_type: str) -> Dict[str, Any]:
        """Generate cache eviction rules."""
        if strategy_type == "aggressive":
            return {
                "policy": "lru_with_frequency",
                "frequency_weight": 0.7,
                "size_threshold": 0.9
            }
        elif strategy_type == "balanced":
            return {
                "policy": "lru",
                "size_threshold": 0.8
            }
        else:
            return {
                "policy": "ttl_strict",
                "size_threshold": 0.7
            }

    def _generate_shared_cache_config(self,
                                    usage_pattern: UsagePattern,
                                    strategy_type: str) -> Dict[str, Any]:
        """Generate shared cache configuration."""
        if usage_pattern.team_size > 5 and strategy_type in ["aggressive", "balanced"]:
            return {
                "enabled": True,
                "cache_server": "team-cache.company.com",
                "upload_threshold": 10,  # MB
                "compression": True,
                "encryption": True
            }
        else:
            return {"enabled": False}

    def _estimate_cache_improvements(self,
                                   usage_pattern: UsagePattern,
                                   cache_strategy: CacheStrategy) -> Dict[str, str]:
        """Estimate cache performance improvements."""
        current_avg_hit_rate = statistics.mean(usage_pattern.cache_hit_rates.values()) if usage_pattern.cache_hit_rates else 0.5
        
        if cache_strategy.strategy_type == "aggressive":
            projected_hit_rate = min(0.9, current_avg_hit_rate + 0.3)
        elif cache_strategy.strategy_type == "balanced":
            projected_hit_rate = min(0.8, current_avg_hit_rate + 0.2)
        else:
            projected_hit_rate = min(0.7, current_avg_hit_rate + 0.1)
        
        improvement = (projected_hit_rate - current_avg_hit_rate) * 100
        
        return {
            "cache_hit_rate": f"+{improvement:.1f}%",
            "build_time": f"-{improvement * 0.5:.1f}%",
            "network_usage": f"-{improvement * 0.3:.1f}%"
        }

    def _generate_cache_implementation_steps(self, cache_strategy: CacheStrategy) -> List[str]:
        """Generate cache implementation steps."""
        steps = [
            "Update .buckconfig with new cache settings",
            "Configure cache size and TTL policies",
            "Set up monitoring for cache performance"
        ]
        
        if cache_strategy.shared_cache_config.get("enabled"):
            steps.extend([
                "Configure shared cache server connection",
                "Set up authentication for shared cache",
                "Test shared cache connectivity"
            ])
        
        if cache_strategy.prefetch_targets:
            steps.append("Configure prefetch for high-frequency targets")
        
        return steps

    def _define_cache_monitoring_metrics(self) -> List[str]:
        """Define cache monitoring metrics."""
        return [
            "cache_hit_rate",
            "cache_miss_rate", 
            "cache_size_utilization",
            "average_build_time",
            "cache_eviction_rate",
            "network_cache_upload_rate",
            "network_cache_download_rate"
        ]

    def _analyze_build_optimizations(self, usage_pattern: UsagePattern) -> List[WorkflowImprovement]:
        """Analyze build optimization opportunities."""
        improvements = []
        
        # Check for slow builds
        slow_targets = []
        for target, times in usage_pattern.build_times.items():
            if times and statistics.mean(times) > 10.0:  # Slower than 10 seconds
                slow_targets.append(target)
        
        if slow_targets:
            improvements.append(WorkflowImprovement(
                improvement_type="build_optimization",
                title="Optimize slow-building targets",
                description=f"Targets {slow_targets} have slow build times. Consider dependency optimization or parallel builds.",
                priority="high",
                estimated_impact="high",
                implementation_effort="medium",
                implementation_steps=[
                    "Analyze dependency graph for slow targets",
                    "Identify opportunities for parallel compilation",
                    "Consider breaking large protos into smaller modules"
                ],
                success_metrics=["average_build_time", "build_time_p95"],
                estimated_time_savings="30-50% build time reduction"
            ))
        
        # Check for build frequency vs cache performance
        high_freq_low_cache = []
        for target in usage_pattern.schema_targets:
            freq = usage_pattern.build_frequency.get(target, 0)
            hit_rate = usage_pattern.cache_hit_rates.get(target, 0)
            if freq > 20 and hit_rate < 0.6:  # High frequency, low cache hit rate
                high_freq_low_cache.append(target)
        
        if high_freq_low_cache:
            improvements.append(WorkflowImprovement(
                improvement_type="build_optimization",
                title="Improve caching for frequently built targets",
                description=f"Targets {high_freq_low_cache} are built frequently but have poor cache performance.",
                priority="medium",
                estimated_impact="medium",
                implementation_effort="low",
                implementation_steps=[
                    "Review cache invalidation patterns",
                    "Consider pinning dependencies",
                    "Optimize build rule determinism"
                ],
                success_metrics=["cache_hit_rate", "build_frequency_efficiency"]
            ))
        
        return improvements

    def _analyze_dependency_optimizations(self, usage_pattern: UsagePattern) -> List[WorkflowImprovement]:
        """Analyze dependency optimization opportunities."""
        improvements = []
        
        # Check for over-dependencies (targets depending on too many others)
        over_dependent_targets = []
        for target, deps in usage_pattern.dependency_patterns.items():
            if len(deps) > 5:  # Arbitrary threshold
                over_dependent_targets.append(target)
        
        if over_dependent_targets:
            improvements.append(WorkflowImprovement(
                improvement_type="dependency_management",
                title="Reduce over-dependencies",
                description=f"Targets {over_dependent_targets} have many dependencies, which may slow builds.",
                priority="medium",
                estimated_impact="medium",
                implementation_effort="high",
                implementation_steps=[
                    "Audit dependency necessity",
                    "Extract common dependencies to shared modules",
                    "Consider dependency injection patterns"
                ],
                success_metrics=["dependency_count", "build_time", "change_impact_radius"]
            ))
        
        return improvements

    def _analyze_automation_opportunities(self, usage_pattern: UsagePattern) -> List[WorkflowImprovement]:
        """Analyze automation opportunities."""
        improvements = []
        
        # Check if team would benefit from automated dependency updates
        if usage_pattern.team_size > 3:
            improvements.append(WorkflowImprovement(
                improvement_type="automation",
                title="Automate dependency updates",
                description="Set up automated updates for protobuf dependencies to reduce manual maintenance.",
                priority="low",
                estimated_impact="medium",
                implementation_effort="medium",
                implementation_steps=[
                    "Set up automated dependency scanning",
                    "Configure update policies",
                    "Implement automated testing for updates"
                ],
                success_metrics=["manual_update_frequency", "security_vulnerability_count"]
            ))
        
        # Check for automation based on build frequency
        total_builds = sum(usage_pattern.build_frequency.values())
        if total_builds > 100:  # High build frequency
            improvements.append(WorkflowImprovement(
                improvement_type="automation",
                title="Implement build result caching",
                description="High build frequency indicates potential for build result caching and artifact reuse.",
                priority="high",
                estimated_impact="high",
                implementation_effort="medium",
                implementation_steps=[
                    "Set up remote build result caching",
                    "Configure artifact sharing",
                    "Implement build fingerprinting"
                ],
                success_metrics=["build_cache_hit_rate", "total_build_time"],
                estimated_time_savings="40-60% reduction in build times"
            ))
        
        return improvements

    def _analyze_workflow_specific_optimizations(self, usage_pattern: UsagePattern) -> List[WorkflowImprovement]:
        """Analyze workflow-specific optimizations."""
        improvements = []
        
        # Check team characteristics for workflow optimizations
        if usage_pattern.workflow_characteristics.get("ci_cd_frequency") == "high":
            improvements.append(WorkflowImprovement(
                improvement_type="automation",
                title="Optimize CI/CD pipeline for protobuf builds",
                description="High CI/CD frequency suggests potential for pipeline optimization and parallel builds.",
                priority="medium",
                estimated_impact="medium",
                implementation_effort="medium",
                implementation_steps=[
                    "Implement parallel protobuf compilation in CI",
                    "Cache protobuf artifacts between CI runs",
                    "Optimize Docker layer caching for proto builds"
                ],
                success_metrics=["ci_build_time", "pipeline_success_rate"]
            ))
        
        # Check for testing strategy optimizations
        if usage_pattern.workflow_characteristics.get("testing_strategy") == "comprehensive":
            improvements.append(WorkflowImprovement(
                improvement_type="automation",
                title="Optimize comprehensive testing strategy",
                description="Comprehensive testing can benefit from incremental testing and smart test selection.",
                priority="low",
                estimated_impact="medium",
                implementation_effort="medium",
                implementation_steps=[
                    "Implement incremental testing for proto changes",
                    "Set up test impact analysis",
                    "Configure smart test selection based on changed protos"
                ],
                success_metrics=["test_execution_time", "test_coverage_efficiency"]
            ))
        
        return improvements

    def _priority_score(self, priority: str) -> int:
        """Convert priority to numeric score."""
        scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        return scores.get(priority, 0)

    def _impact_score(self, impact: str) -> int:
        """Convert impact to numeric score."""
        scores = {"high": 3, "medium": 2, "low": 1}
        return scores.get(impact, 0)

    def _get_performance_baseline(self, team_name: str) -> Dict[str, float]:
        """Get performance baseline for team."""
        try:
            with open(self.performance_baselines_file, 'r') as f:
                baselines = json.load(f)
            return baselines.get(team_name, {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _analyze_current_performance(self, usage_pattern: UsagePattern) -> Dict[str, Any]:
        """Analyze current performance metrics."""
        # Calculate average build times
        avg_build_times = {}
        for target, times in usage_pattern.build_times.items():
            if times:
                avg_build_times[target] = statistics.mean(times)
        
        overall_avg_build_time = statistics.mean(avg_build_times.values()) if avg_build_times else 0
        
        # Calculate overall cache hit rate
        overall_cache_hit_rate = statistics.mean(usage_pattern.cache_hit_rates.values()) if usage_pattern.cache_hit_rates else 0
        
        # Calculate build frequency metrics
        total_builds_per_day = sum(usage_pattern.build_frequency.values())
        builds_per_developer = total_builds_per_day / max(usage_pattern.active_developers, 1)
        
        return {
            "average_build_time": overall_avg_build_time,
            "cache_hit_rate": overall_cache_hit_rate,
            "total_builds_per_day": total_builds_per_day,
            "builds_per_developer_per_day": builds_per_developer,
            "target_count": len(usage_pattern.schema_targets),
            "team_efficiency_score": self._calculate_team_efficiency_score(usage_pattern)
        }

    def _calculate_team_efficiency_score(self, usage_pattern: UsagePattern) -> float:
        """Calculate overall team efficiency score."""
        # Combine multiple factors into a single efficiency score (0-100)
        
        # Cache efficiency (0-40 points)
        avg_cache_hit_rate = statistics.mean(usage_pattern.cache_hit_rates.values()) if usage_pattern.cache_hit_rates else 0
        cache_score = avg_cache_hit_rate * 40
        
        # Build time efficiency (0-30 points)
        avg_build_times = [statistics.mean(times) for times in usage_pattern.build_times.values() if times]
        if avg_build_times:
            # Inverse relationship: faster builds = higher score
            avg_build_time = statistics.mean(avg_build_times)
            build_score = max(0, 30 - (avg_build_time / 10) * 30)  # 10s = 0 points, 0s = 30 points
        else:
            build_score = 15  # Default middle score
        
        # Team utilization (0-30 points)
        total_builds = sum(usage_pattern.build_frequency.values())
        builds_per_dev = total_builds / max(usage_pattern.active_developers, 1)
        utilization_score = min(30, builds_per_dev / 20 * 30)  # 20 builds/dev/day = max score
        
        return cache_score + build_score + utilization_score

    def _project_improvements(self,
                            usage_pattern: UsagePattern,
                            cache_strategy: CacheStrategy,
                            workflow_improvements: List[WorkflowImprovement]) -> Dict[str, str]:
        """Project performance improvements."""
        improvements = {}
        
        # Cache improvements
        for metric, improvement in cache_strategy.estimated_improvement.items():
            improvements[f"cache_{metric}"] = improvement
        
        # Workflow improvements
        high_impact_improvements = [w for w in workflow_improvements if w.estimated_impact == "high"]
        if high_impact_improvements:
            improvements["overall_productivity"] = f"+{len(high_impact_improvements) * 15}%"
        
        # Build time improvements
        if any("build_optimization" in w.improvement_type for w in workflow_improvements):
            improvements["build_efficiency"] = "+25-40%"
        
        # Team efficiency score improvement
        current_score = self._calculate_team_efficiency_score(usage_pattern)
        projected_score = min(100, current_score + len(workflow_improvements) * 5)
        improvements["team_efficiency_score"] = f"+{projected_score - current_score:.1f} points"
        
        return improvements

    def _generate_implementation_roadmap(self,
                                       cache_strategy: CacheStrategy,
                                       workflow_improvements: List[WorkflowImprovement]) -> List[Dict[str, Any]]:
        """Generate implementation roadmap."""
        roadmap = []
        
        # Phase 1: Quick wins (low effort, high impact)
        quick_wins = [w for w in workflow_improvements 
                     if w.implementation_effort in ["minimal", "low"] and w.estimated_impact in ["medium", "high"]]
        
        if quick_wins or cache_strategy.strategy_type == "conservative":
            roadmap.append({
                "phase": 1,
                "name": "Quick Wins",
                "duration": "1-2 weeks",
                "items": [w.title for w in quick_wins] + ["Implement basic cache optimizations"],
                "prerequisites": [],
                "success_metrics": ["cache_hit_rate", "build_time"]
            })
        
        # Phase 2: Cache optimization
        if cache_strategy.strategy_type in ["balanced", "aggressive"]:
            roadmap.append({
                "phase": 2,
                "name": "Cache Optimization",
                "duration": "2-3 weeks",
                "items": cache_strategy.implementation_steps,
                "prerequisites": ["Phase 1 complete"],
                "success_metrics": cache_strategy.monitoring_metrics
            })
        
        # Phase 3: Workflow improvements (medium/high effort)
        major_improvements = [w for w in workflow_improvements 
                            if w.implementation_effort in ["medium", "high"]]
        
        if major_improvements:
            roadmap.append({
                "phase": 3,
                "name": "Workflow Optimization",
                "duration": "4-6 weeks",
                "items": [w.title for w in major_improvements],
                "prerequisites": ["Phase 2 complete"],
                "success_metrics": ["team_efficiency_score", "overall_productivity"]
            })
        
        return roadmap

    def _save_usage_pattern(self, team_name: str, usage_pattern: UsagePattern) -> None:
        """Save usage pattern to storage."""
        try:
            with open(self.usage_patterns_file, 'r') as f:
                patterns = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            patterns = {}
        
        patterns[team_name] = asdict(usage_pattern)
        
        with open(self.usage_patterns_file, 'w') as f:
            json.dump(patterns, f, indent=2)

    def _save_cache_strategy(self, team_name: str, cache_strategy: CacheStrategy) -> None:
        """Save cache strategy to storage."""
        try:
            with open(self.cache_strategies_file, 'r') as f:
                strategies = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            strategies = {}
        
        strategies[team_name] = asdict(cache_strategy)
        
        with open(self.cache_strategies_file, 'w') as f:
            json.dump(strategies, f, indent=2)

    def _save_optimization_report(self, team_name: str, report: TeamOptimizationReport) -> None:
        """Save optimization report to storage."""
        try:
            with open(self.optimization_reports_file, 'r') as f:
                reports = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            reports = {}
        
        # Convert report to dict, handling nested dataclasses
        report_dict = asdict(report)
        
        reports[team_name] = report_dict
        
        with open(self.optimization_reports_file, 'w') as f:
            json.dump(reports, f, indent=2)


def main():
    """Main entry point for team performance optimizer testing."""
    parser = argparse.ArgumentParser(description="Team Performance Optimizer")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze usage patterns
    patterns_parser = subparsers.add_parser("analyze-patterns", help="Analyze team usage patterns")
    patterns_parser.add_argument("--team", required=True, help="Team name")
    patterns_parser.add_argument("--period", default="7d", choices=["1d", "7d", "30d"], help="Analysis period")
    
    # Optimize caching
    cache_parser = subparsers.add_parser("optimize-cache", help="Generate cache optimization strategy")
    cache_parser.add_argument("--team", required=True, help="Team name")
    
    # Workflow improvements
    workflow_parser = subparsers.add_parser("workflow-improvements", help="Get workflow improvement recommendations")
    workflow_parser.add_argument("--team", required=True, help="Team name")
    
    # Generate optimization report
    report_parser = subparsers.add_parser("optimization-report", help="Generate comprehensive optimization report")
    report_parser.add_argument("--team", required=True, help="Team name")
    report_parser.add_argument("--period", default="7d", choices=["1d", "7d", "30d"], help="Analysis period")
    report_parser.add_argument("--output", help="Output file for report")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        optimizer = TeamPerformanceOptimizer(
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "analyze-patterns":
            patterns = optimizer.analyze_team_usage_patterns(args.team, args.period)
            
            print(f"📊 Usage Patterns for Team {args.team}")
            print(f"   Analysis period: {patterns.analysis_period}")
            print(f"   Team size: {patterns.team_size}")
            print(f"   Active developers: {patterns.active_developers}")
            print(f"   Schema targets: {len(patterns.schema_targets)}")
            print(f"   Total builds/day: {sum(patterns.build_frequency.values())}")
            
            if patterns.cache_hit_rates:
                avg_hit_rate = statistics.mean(patterns.cache_hit_rates.values())
                print(f"   Average cache hit rate: {avg_hit_rate:.1%}")
            
            if patterns.build_times:
                all_times = [time for times in patterns.build_times.values() for time in times]
                if all_times:
                    avg_build_time = statistics.mean(all_times)
                    print(f"   Average build time: {avg_build_time:.1f}s")
        
        elif args.command == "optimize-cache":
            cache_strategy = optimizer.optimize_caching_strategy(args.team)
            
            print(f"🚀 Cache Strategy for Team {args.team}")
            print(f"   Strategy type: {cache_strategy.strategy_type}")
            print(f"   Prefetch targets: {len(cache_strategy.prefetch_targets)}")
            
            print(f"\n   Estimated improvements:")
            for metric, improvement in cache_strategy.estimated_improvement.items():
                print(f"     {metric}: {improvement}")
            
            print(f"\n   Implementation steps:")
            for i, step in enumerate(cache_strategy.implementation_steps, 1):
                print(f"     {i}. {step}")
        
        elif args.command == "workflow-improvements":
            improvements = optimizer.recommend_workflow_improvements(args.team)
            
            print(f"💡 Workflow Improvements for Team {args.team}")
            if improvements:
                for improvement in improvements:
                    print(f"\n   {improvement.title}")
                    print(f"     Type: {improvement.improvement_type}")
                    print(f"     Priority: {improvement.priority}")
                    print(f"     Impact: {improvement.estimated_impact}")
                    print(f"     Effort: {improvement.implementation_effort}")
                    print(f"     Description: {improvement.description}")
                    if improvement.estimated_time_savings:
                        print(f"     Time savings: {improvement.estimated_time_savings}")
            else:
                print("   No improvements identified")
        
        elif args.command == "optimization-report":
            report = optimizer.generate_optimization_report(args.team, args.period)
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(asdict(report), f, indent=2)
                print(f"📋 Optimization report saved to {args.output}")
            else:
                print(f"📋 Optimization Report for Team {args.team}")
                print(f"   Generated: {report.generated_at}")
                print(f"   Analysis period: {report.analysis_period}")
                
                print(f"\n   Current Performance:")
                for metric, value in report.current_performance.items():
                    print(f"     {metric}: {value}")
                
                print(f"\n   Projected Improvements:")
                for metric, improvement in report.projected_improvements.items():
                    print(f"     {metric}: {improvement}")
                
                print(f"\n   Implementation Roadmap:")
                for phase in report.implementation_roadmap:
                    print(f"     Phase {phase['phase']}: {phase['name']} ({phase['duration']})")
                    for item in phase['items']:
                        print(f"       - {item}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
