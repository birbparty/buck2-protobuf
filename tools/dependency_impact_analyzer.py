#!/usr/bin/env python3
"""
Dependency Impact Analyzer for Team Collaboration.

This module provides advanced dependency impact analysis for protobuf schema changes,
identifying affected services, teams, and cross-system dependencies to enable
proactive coordination and migration planning.
"""

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials
from .bsr_teams import BSRTeamManager, Team
from .bsr_breaking_change_detector import BSRBreakingChangeDetector, BreakingChange
from .schema_governance_engine import SchemaChange

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ServiceDependency:
    """Represents a service dependency on a schema."""
    service_name: str
    service_repository: str
    dependency_type: str  # "direct", "transitive", "optional"
    usage_pattern: str  # "consumer", "producer", "both"
    schema_files: List[str] = field(default_factory=list)
    dependency_strength: str = "medium"  # "weak", "medium", "strong", "critical"
    team_owner: Optional[str] = None
    contact_info: Optional[Dict[str, str]] = None
    migration_complexity: str = "unknown"  # "trivial", "simple", "moderate", "complex", "critical"
    last_updated: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))


@dataclass
class DependencyGraph:
    """Represents a complete dependency graph for schema analysis."""
    schema_target: str
    direct_dependencies: List[ServiceDependency] = field(default_factory=list)
    transitive_dependencies: List[ServiceDependency] = field(default_factory=list)
    reverse_dependencies: List[ServiceDependency] = field(default_factory=list)
    dependency_matrix: Dict[str, List[str]] = field(default_factory=dict)
    analysis_metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))


@dataclass
class TeamImpact:
    """Represents the impact of a change on a specific team."""
    team_name: str
    impact_level: str  # "none", "low", "medium", "high", "critical"
    affected_services: List[str] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)
    estimated_effort: Optional[str] = None  # "1h", "1d", "1w", etc.
    migration_deadline: Optional[str] = None
    risk_factors: List[str] = field(default_factory=list)
    mitigation_strategies: List[str] = field(default_factory=list)
    contact_priority: str = "normal"  # "low", "normal", "high", "urgent"


@dataclass
class CrossSystemImpact:
    """Represents impact across different systems and boundaries."""
    affected_systems: List[str] = field(default_factory=list)
    cross_team_dependencies: Dict[str, List[str]] = field(default_factory=dict)
    external_dependencies: List[str] = field(default_factory=list)
    cascade_effects: List[Dict[str, Any]] = field(default_factory=list)
    coordination_requirements: List[str] = field(default_factory=list)


@dataclass
class MigrationPlan:
    """Comprehensive migration plan for schema changes."""
    change_id: str
    migration_strategy: str  # "immediate", "phased", "coordinated", "delayed"
    phases: List[Dict[str, Any]] = field(default_factory=list)
    dependencies_order: List[str] = field(default_factory=list)
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    testing_strategy: Dict[str, Any] = field(default_factory=dict)
    communication_plan: Dict[str, Any] = field(default_factory=dict)
    timeline: Dict[str, str] = field(default_factory=dict)
    risk_assessment: Dict[str, Any] = field(default_factory=dict)


class DependencyAnalysisError(Exception):
    """Dependency analysis operation failed."""
    pass


class DependencyImpactAnalyzer:
    """
    Advanced dependency impact analysis system.
    
    Analyzes schema changes across team boundaries, identifies affected services,
    and provides comprehensive migration planning with cross-system coordination.
    """
    
    def __init__(self,
                 storage_dir: Union[str, Path] = None,
                 team_manager: Optional[BSRTeamManager] = None,
                 breaking_change_detector: Optional[BSRBreakingChangeDetector] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 verbose: bool = False):
        """
        Initialize Dependency Impact Analyzer.
        
        Args:
            storage_dir: Directory for dependency analysis storage
            team_manager: BSR team manager instance
            breaking_change_detector: Breaking change detector instance
            bsr_authenticator: BSR authentication instance
            verbose: Enable verbose logging
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'dependency-analysis'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Storage files
        self.dependency_registry_file = self.storage_dir / "dependency_registry.json"
        self.service_catalog_file = self.storage_dir / "service_catalog.json"
        self.analysis_cache_file = self.storage_dir / "analysis_cache.json"
        self.migration_plans_file = self.storage_dir / "migration_plans.json"
        
        # Dependencies
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        self.breaking_change_detector = breaking_change_detector or BSRBreakingChangeDetector(verbose=verbose)
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Initialize storage and load data
        self._init_storage()
        self.dependency_registry = self._load_dependency_registry()
        self.service_catalog = self._load_service_catalog()
        
        logger.info(f"Dependency Impact Analyzer initialized")

    def _init_storage(self) -> None:
        """Initialize storage files."""
        for file_path in [self.dependency_registry_file, self.service_catalog_file,
                         self.analysis_cache_file, self.migration_plans_file]:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump({}, f)

    def _load_dependency_registry(self) -> Dict[str, List[ServiceDependency]]:
        """Load dependency registry from storage."""
        try:
            with open(self.dependency_registry_file, 'r') as f:
                registry_data = json.load(f)
            
            registry = {}
            for schema_target, dependencies_data in registry_data.items():
                dependencies = []
                for dep_data in dependencies_data:
                    dependencies.append(ServiceDependency(**dep_data))
                registry[schema_target] = dependencies
            
            return registry
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_dependency_registry(self, registry: Dict[str, List[ServiceDependency]]) -> None:
        """Save dependency registry to storage."""
        try:
            registry_data = {}
            for schema_target, dependencies in registry.items():
                registry_data[schema_target] = [asdict(dep) for dep in dependencies]
            
            with open(self.dependency_registry_file, 'w') as f:
                json.dump(registry_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save dependency registry: {e}")

    def _load_service_catalog(self) -> Dict[str, Dict[str, Any]]:
        """Load service catalog from storage."""
        try:
            with open(self.service_catalog_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_service_catalog(self, catalog: Dict[str, Dict[str, Any]]) -> None:
        """Save service catalog to storage."""
        try:
            with open(self.service_catalog_file, 'w') as f:
                json.dump(catalog, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save service catalog: {e}")

    def register_service_dependency(self,
                                  schema_target: str,
                                  service_dependency: ServiceDependency) -> None:
        """
        Register a service dependency on a schema.
        
        Args:
            schema_target: Schema target being depended upon
            service_dependency: Service dependency information
        """
        if schema_target not in self.dependency_registry:
            self.dependency_registry[schema_target] = []
        
        # Check if dependency already exists and update it
        existing_idx = None
        for i, existing_dep in enumerate(self.dependency_registry[schema_target]):
            if existing_dep.service_name == service_dependency.service_name:
                existing_idx = i
                break
        
        if existing_idx is not None:
            self.dependency_registry[schema_target][existing_idx] = service_dependency
            logger.info(f"Updated dependency: {service_dependency.service_name} -> {schema_target}")
        else:
            self.dependency_registry[schema_target].append(service_dependency)
            logger.info(f"Registered dependency: {service_dependency.service_name} -> {schema_target}")
        
        self._save_dependency_registry(self.dependency_registry)

    def register_service(self,
                        service_name: str,
                        service_info: Dict[str, Any]) -> None:
        """
        Register a service in the service catalog.
        
        Args:
            service_name: Name of the service
            service_info: Service metadata and configuration
        """
        self.service_catalog[service_name] = {
            **service_info,
            "registered_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        self._save_service_catalog(self.service_catalog)
        logger.info(f"Registered service: {service_name}")

    def analyze_dependency_graph(self, schema_target: str) -> DependencyGraph:
        """
        Build comprehensive dependency graph for a schema.
        
        Args:
            schema_target: Schema target to analyze
            
        Returns:
            Complete dependency graph
        """
        graph = DependencyGraph(schema_target=schema_target)
        
        # Get direct dependencies
        direct_deps = self.dependency_registry.get(schema_target, [])
        graph.direct_dependencies = direct_deps
        
        # Analyze transitive dependencies
        graph.transitive_dependencies = self._analyze_transitive_dependencies(schema_target, direct_deps)
        
        # Analyze reverse dependencies (who depends on this schema's dependencies)
        graph.reverse_dependencies = self._analyze_reverse_dependencies(schema_target)
        
        # Build dependency matrix for visualization
        graph.dependency_matrix = self._build_dependency_matrix(schema_target, graph)
        
        # Add analysis metadata
        graph.analysis_metadata = {
            "total_affected_services": len(graph.direct_dependencies) + len(graph.transitive_dependencies),
            "critical_dependencies": len([d for d in graph.direct_dependencies if d.dependency_strength == "critical"]),
            "teams_affected": len(set([d.team_owner for d in graph.direct_dependencies if d.team_owner])),
            "complexity_score": self._calculate_complexity_score(graph)
        }
        
        return graph

    def identify_affected_services(self, 
                                 schema_target: str,
                                 breaking_changes: List[BreakingChange] = None) -> List[Dict[str, Any]]:
        """
        Identify services affected by schema changes.
        
        Args:
            schema_target: Schema target being changed
            breaking_changes: List of breaking changes (if any)
            
        Returns:
            List of affected services with impact details
        """
        affected_services = []
        
        # Get dependency graph
        dependency_graph = self.analyze_dependency_graph(schema_target)
        
        # Analyze impact for each dependent service
        all_dependencies = dependency_graph.direct_dependencies + dependency_graph.transitive_dependencies
        
        for dependency in all_dependencies:
            service_impact = self._analyze_service_impact(dependency, breaking_changes)
            affected_services.append(service_impact)
        
        # Sort by impact severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
        affected_services.sort(key=lambda s: severity_order.get(s.get("impact_level", "none"), 4))
        
        return affected_services

    def analyze_team_impacts(self,
                           schema_target: str,
                           breaking_changes: List[BreakingChange] = None) -> List[TeamImpact]:
        """
        Analyze impact of schema changes on teams.
        
        Args:
            schema_target: Schema target being changed
            breaking_changes: List of breaking changes
            
        Returns:
            List of team impacts
        """
        team_impacts = {}
        
        # Get affected services
        affected_services = self.identify_affected_services(schema_target, breaking_changes)
        
        # Group services by team
        for service_info in affected_services:
            team_name = service_info.get("team_owner")
            if not team_name:
                continue
            
            if team_name not in team_impacts:
                team_impacts[team_name] = TeamImpact(
                    team_name=team_name,
                    impact_level="none"
                )
            
            team_impact = team_impacts[team_name]
            
            # Add affected service
            team_impact.affected_services.append(service_info["service_name"])
            
            # Update impact level (take highest)
            current_level = team_impact.impact_level
            service_level = service_info.get("impact_level", "none")
            if self._compare_impact_levels(service_level, current_level) > 0:
                team_impact.impact_level = service_level
            
            # Add required actions
            if service_info.get("migration_required"):
                team_impact.required_actions.append(f"Migrate {service_info['service_name']}")
            
            if service_info.get("testing_required"):
                team_impact.required_actions.append(f"Test {service_info['service_name']}")
            
            # Estimate effort
            if not team_impact.estimated_effort:
                team_impact.estimated_effort = service_info.get("migration_complexity", "unknown")
            
            # Add risk factors
            if breaking_changes:
                team_impact.risk_factors.extend([
                    f"Breaking changes in {schema_target}",
                    f"Service {service_info['service_name']} affected"
                ])
        
        # Generate mitigation strategies for each team
        for team_impact in team_impacts.values():
            team_impact.mitigation_strategies = self._generate_mitigation_strategies(team_impact)
            
            # Set contact priority based on impact
            if team_impact.impact_level in ["critical", "high"]:
                team_impact.contact_priority = "urgent"
            elif team_impact.impact_level == "medium":
                team_impact.contact_priority = "high"
        
        return list(team_impacts.values())

    def analyze_cross_system_impact(self,
                                  schema_target: str,
                                  breaking_changes: List[BreakingChange] = None) -> CrossSystemImpact:
        """
        Analyze impact across different systems and organizational boundaries.
        
        Args:
            schema_target: Schema target being changed
            breaking_changes: List of breaking changes
            
        Returns:
            Cross-system impact analysis
        """
        impact = CrossSystemImpact()
        
        # Get dependency graph
        dependency_graph = self.analyze_dependency_graph(schema_target)
        
        # Identify affected systems
        systems = set()
        for dependency in dependency_graph.direct_dependencies + dependency_graph.transitive_dependencies:
            service_info = self.service_catalog.get(dependency.service_name, {})
            system = service_info.get("system", "unknown")
            systems.add(system)
        
        impact.affected_systems = list(systems)
        
        # Analyze cross-team dependencies
        team_deps = {}
        for dependency in dependency_graph.direct_dependencies:
            if dependency.team_owner:
                if dependency.team_owner not in team_deps:
                    team_deps[dependency.team_owner] = []
                team_deps[dependency.team_owner].append(dependency.service_name)
        
        impact.cross_team_dependencies = team_deps
        
        # Identify external dependencies (services not in our catalog)
        external_deps = []
        for dependency in dependency_graph.direct_dependencies:
            if dependency.service_name not in self.service_catalog:
                external_deps.append(dependency.service_name)
        
        impact.external_dependencies = external_deps
        
        # Analyze cascade effects
        impact.cascade_effects = self._analyze_cascade_effects(dependency_graph, breaking_changes)
        
        # Generate coordination requirements
        impact.coordination_requirements = self._generate_coordination_requirements(impact)
        
        return impact

    def generate_migration_plan(self,
                              change_id: str,
                              schema_target: str,
                              breaking_changes: List[BreakingChange] = None) -> MigrationPlan:
        """
        Generate comprehensive migration plan for schema changes.
        
        Args:
            change_id: Unique identifier for the change
            schema_target: Schema target being changed
            breaking_changes: List of breaking changes
            
        Returns:
            Comprehensive migration plan
        """
        plan = MigrationPlan(change_id=change_id)
        
        # Analyze impacts
        dependency_graph = self.analyze_dependency_graph(schema_target)
        team_impacts = self.analyze_team_impacts(schema_target, breaking_changes)
        cross_system_impact = self.analyze_cross_system_impact(schema_target, breaking_changes)
        
        # Determine migration strategy
        plan.migration_strategy = self._determine_migration_strategy(
            dependency_graph, team_impacts, cross_system_impact, breaking_changes
        )
        
        # Create migration phases
        plan.phases = self._create_migration_phases(
            dependency_graph, team_impacts, plan.migration_strategy
        )
        
        # Determine dependencies order
        plan.dependencies_order = self._calculate_migration_order(dependency_graph, team_impacts)
        
        # Create rollback plan
        plan.rollback_plan = self._create_rollback_plan(schema_target, dependency_graph)
        
        # Create testing strategy
        plan.testing_strategy = self._create_testing_strategy(dependency_graph, breaking_changes)
        
        # Create communication plan
        plan.communication_plan = self._create_communication_plan(team_impacts, cross_system_impact)
        
        # Create timeline
        plan.timeline = self._create_migration_timeline(plan.phases, team_impacts)
        
        # Risk assessment
        plan.risk_assessment = self._create_risk_assessment(
            dependency_graph, breaking_changes, cross_system_impact
        )
        
        # Save migration plan
        self._save_migration_plan(change_id, plan)
        
        return plan

    def get_migration_recommendations(self,
                                    schema_target: str,
                                    breaking_changes: List[BreakingChange] = None) -> List[str]:
        """
        Generate migration recommendations based on dependency analysis.
        
        Args:
            schema_target: Schema target being changed
            breaking_changes: List of breaking changes
            
        Returns:
            List of migration recommendations
        """
        recommendations = []
        
        # Analyze dependencies
        dependency_graph = self.analyze_dependency_graph(schema_target)
        team_impacts = self.analyze_team_impacts(schema_target, breaking_changes)
        
        # Generate recommendations based on analysis
        if dependency_graph.analysis_metadata.get("total_affected_services", 0) > 10:
            recommendations.append("Consider phased migration due to high number of affected services")
        
        critical_deps = dependency_graph.analysis_metadata.get("critical_dependencies", 0)
        if critical_deps > 0:
            recommendations.append(f"Exercise extreme caution: {critical_deps} critical dependencies identified")
        
        high_impact_teams = len([t for t in team_impacts if t.impact_level in ["critical", "high"]])
        if high_impact_teams > 0:
            recommendations.append(f"Coordinate with {high_impact_teams} high-impact teams before migration")
        
        if breaking_changes:
            recommendations.append("Implement comprehensive testing due to breaking changes")
            recommendations.append("Prepare detailed migration documentation for affected teams")
        
        # Team-specific recommendations
        for team_impact in team_impacts:
            if team_impact.impact_level in ["critical", "high"]:
                recommendations.append(
                    f"Priority coordination with {team_impact.team_name} team required"
                )
        
        # Complexity-based recommendations
        complexity_score = dependency_graph.analysis_metadata.get("complexity_score", 0)
        if complexity_score > 7:
            recommendations.append("High complexity migration - consider external coordination support")
        elif complexity_score > 5:
            recommendations.append("Medium complexity migration - ensure adequate planning time")
        
        return recommendations

    # Helper methods
    
    def _analyze_transitive_dependencies(self,
                                       schema_target: str,
                                       direct_deps: List[ServiceDependency]) -> List[ServiceDependency]:
        """Analyze transitive dependencies."""
        transitive_deps = []
        
        # For each direct dependency, check if it has dependencies on other schemas
        for dep in direct_deps:
            service_info = self.service_catalog.get(dep.service_name, {})
            service_dependencies = service_info.get("schema_dependencies", [])
            
            for schema_dep in service_dependencies:
                if schema_dep != schema_target:  # Avoid circular references
                    # Check if this schema has dependencies
                    indirect_deps = self.dependency_registry.get(schema_dep, [])
                    for indirect_dep in indirect_deps:
                        if indirect_dep.service_name != dep.service_name:  # Avoid self-reference
                            transitive_dep = ServiceDependency(
                                service_name=indirect_dep.service_name,
                                service_repository=indirect_dep.service_repository,
                                dependency_type="transitive",
                                usage_pattern=indirect_dep.usage_pattern,
                                dependency_strength="weak",  # Transitive deps are typically weaker
                                team_owner=indirect_dep.team_owner
                            )
                            transitive_deps.append(transitive_dep)
        
        return transitive_deps

    def _analyze_reverse_dependencies(self, schema_target: str) -> List[ServiceDependency]:
        """Analyze reverse dependencies (what this schema depends on)."""
        reverse_deps = []
        
        # Look through all dependency registrations to find what this schema depends on
        for target, dependencies in self.dependency_registry.items():
            for dep in dependencies:
                if dep.service_name in schema_target or schema_target in dep.service_repository:
                    # This is a potential reverse dependency
                    reverse_dep = ServiceDependency(
                        service_name=target,
                        service_repository=target,
                        dependency_type="reverse",
                        usage_pattern="producer",  # This schema produces for others
                        dependency_strength=dep.dependency_strength,
                        team_owner=dep.team_owner
                    )
                    reverse_deps.append(reverse_dep)
        
        return reverse_deps

    def _build_dependency_matrix(self, schema_target: str, graph: DependencyGraph) -> Dict[str, List[str]]:
        """Build dependency matrix for visualization."""
        matrix = {}
        
        # Add direct dependencies
        matrix[schema_target] = [dep.service_name for dep in graph.direct_dependencies]
        
        # Add transitive relationships
        for dep in graph.direct_dependencies:
            service_info = self.service_catalog.get(dep.service_name, {})
            service_deps = service_info.get("schema_dependencies", [])
            matrix[dep.service_name] = service_deps
        
        return matrix

    def _calculate_complexity_score(self, graph: DependencyGraph) -> int:
        """Calculate complexity score based on dependency graph."""
        score = 0
        
        # Base score from number of dependencies
        score += len(graph.direct_dependencies)
        score += len(graph.transitive_dependencies) * 0.5
        
        # Add score for critical dependencies
        critical_deps = len([d for d in graph.direct_dependencies if d.dependency_strength == "critical"])
        score += critical_deps * 2
        
        # Add score for team diversity
        teams = set([d.team_owner for d in graph.direct_dependencies if d.team_owner])
        score += len(teams) * 0.5
        
        return int(score)

    def _analyze_service_impact(self,
                              dependency: ServiceDependency,
                              breaking_changes: List[BreakingChange] = None) -> Dict[str, Any]:
        """Analyze impact on a specific service."""
        impact = {
            "service_name": dependency.service_name,
            "service_repository": dependency.service_repository,
            "team_owner": dependency.team_owner,
            "dependency_type": dependency.dependency_type,
            "usage_pattern": dependency.usage_pattern,
            "dependency_strength": dependency.dependency_strength
        }
        
        # Determine impact level
        if breaking_changes and dependency.dependency_strength in ["critical", "strong"]:
            impact["impact_level"] = "critical"
        elif breaking_changes and dependency.dependency_strength == "medium":
            impact["impact_level"] = "high"
        elif breaking_changes:
            impact["impact_level"] = "medium"
        else:
            impact["impact_level"] = "low"
        
        # Determine if migration is required
        impact["migration_required"] = bool(breaking_changes and dependency.dependency_type == "direct")
        impact["testing_required"] = bool(breaking_changes)
        
        # Migration complexity
        impact["migration_complexity"] = dependency.migration_complexity
        
        return impact

    def _compare_impact_levels(self, level1: str, level2: str) -> int:
        """Compare two impact levels. Returns >0 if level1 > level2."""
        levels = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
        return levels.get(level1, 0) - levels.get(level2, 0)

    def _generate_mitigation_strategies(self, team_impact: TeamImpact) -> List[str]:
        """Generate mitigation strategies for team impact."""
        strategies = []
        
        if team_impact.impact_level in ["critical", "high"]:
            strategies.append("Prioritize immediate team coordination")
            strategies.append("Assign dedicated migration lead")
            strategies.append("Create detailed migration timeline")
        
        if len(team_impact.affected_services) > 3:
            strategies.append("Consider parallel migration of services")
            strategies.append("Implement comprehensive testing strategy")
        
        if team_impact.impact_level == "critical":
            strategies.append("Prepare rollback plan for each service")
            strategies.append("Set up monitoring for migration progress")
        
        return strategies

    def _analyze_cascade_effects(self,
                               dependency_graph: DependencyGraph,
                               breaking_changes: List[BreakingChange] = None) -> List[Dict[str, Any]]:
        """Analyze potential cascade effects of the change."""
        cascade_effects = []
        
        if not breaking_changes:
            return cascade_effects
        
        # Analyze potential cascading failures
        for dep in dependency_graph.direct_dependencies:
            if dep.dependency_strength in ["critical", "strong"]:
                effect = {
                    "service": dep.service_name,
                    "effect_type": "service_disruption",
                    "probability": "high" if dep.dependency_strength == "critical" else "medium",
                    "impact_scope": "team" if dep.team_owner else "unknown",
                    "mitigation": f"Coordinate migration for {dep.service_name}"
                }
                cascade_effects.append(effect)
        
        return cascade_effects

    def _generate_coordination_requirements(self, impact: CrossSystemImpact) -> List[str]:
        """Generate coordination requirements based on cross-system impact."""
        requirements = []
        
        if len(impact.affected_systems) > 1:
            requirements.append("Cross-system coordination required")
        
        if len(impact.cross_team_dependencies) > 2:
            requirements.append("Multi-team coordination meeting recommended")
        
        if impact.external_dependencies:
            requirements.append("External dependency coordination required")
        
        if impact.cascade_effects:
            requirements.append("Cascade effect monitoring required")
        
        return requirements

    def _determine_migration_strategy(self,
                                    dependency_graph: DependencyGraph,
                                    team_impacts: List[TeamImpact],
                                    cross_system_impact: CrossSystemImpact,
                                    breaking_changes: List[BreakingChange] = None) -> str:
        """Determine appropriate migration strategy."""
        # Check for critical factors
        has_critical_deps = any(d.dependency_strength == "critical" for d in dependency_graph.direct_dependencies)
        has_high_impact_teams = any(t.impact_level in ["critical", "high"] for t in team_impacts)
        has_breaking_changes = bool(breaking_changes)
        many_affected_services = len(dependency_graph.direct_dependencies) > 5
        
        if has_critical_deps or (has_breaking_changes and has_high_impact_teams):
            return "coordinated"
        elif many_affected_services or len(cross_system_impact.affected_systems) > 2:
            return "phased"
        elif has_breaking_changes:
            return "immediate"
        else:
            return "immediate"

    def _create_migration_phases(self,
                               dependency_graph: DependencyGraph,
                               team_impacts: List[TeamImpact],
                               migration_strategy: str) -> List[Dict[str, Any]]:
        """Create migration phases based on strategy and dependencies."""
        phases = []
        
        if migration_strategy == "immediate":
            phases.append({
                "phase": 1,
                "name": "Immediate Migration",
                "description": "Deploy all changes simultaneously",
                "services": [dep.service_name for dep in dependency_graph.direct_dependencies],
                "duration": "1-2 hours",
                "parallel": True
            })
        
        elif migration_strategy == "phased":
            # Group services by impact level and dependency strength
            critical_services = [
                dep.service_name for dep in dependency_graph.direct_dependencies
                if dep.dependency_strength == "critical"
            ]
            
            high_impact_services = [
                dep.service_name for dep in dependency_graph.direct_dependencies
                if dep.dependency_strength in ["strong", "medium"] and dep.service_name not in critical_services
            ]
            
            low_impact_services = [
                dep.service_name for dep in dependency_graph.direct_dependencies
                if dep.dependency_strength == "weak" and dep.service_name not in critical_services + high_impact_services
            ]
            
            if critical_services:
                phases.append({
                    "phase": 1,
                    "name": "Critical Services Migration",
                    "description": "Migrate critical dependencies first",
                    "services": critical_services,
                    "duration": "4-8 hours",
                    "parallel": False
                })
            
            if high_impact_services:
                phases.append({
                    "phase": 2,
                    "name": "High Impact Services Migration",
                    "description": "Migrate high impact services",
                    "services": high_impact_services,
                    "duration": "2-4 hours",
                    "parallel": True
                })
            
            if low_impact_services:
                phases.append({
                    "phase": 3,
                    "name": "Low Impact Services Migration",
                    "description": "Migrate remaining services",
                    "services": low_impact_services,
                    "duration": "1-2 hours",
                    "parallel": True
                })
        
        elif migration_strategy == "coordinated":
            # Group by teams for coordinated migration
            team_services = {}
            for dep in dependency_graph.direct_dependencies:
                if dep.team_owner:
                    if dep.team_owner not in team_services:
                        team_services[dep.team_owner] = []
                    team_services[dep.team_owner].append(dep.service_name)
            
            for i, (team, services) in enumerate(team_services.items(), 1):
                phases.append({
                    "phase": i,
                    "name": f"Team {team} Migration",
                    "description": f"Coordinated migration for {team} team",
                    "services": services,
                    "team": team,
                    "duration": "2-6 hours",
                    "parallel": False
                })
        
        return phases

    def _calculate_migration_order(self,
                                 dependency_graph: DependencyGraph,
                                 team_impacts: List[TeamImpact]) -> List[str]:
        """Calculate optimal migration order."""
        # Sort by dependency strength and impact level
        services = []
        
        for dep in dependency_graph.direct_dependencies:
            priority_score = 0
            
            # Score based on dependency strength
            strength_scores = {"critical": 4, "strong": 3, "medium": 2, "weak": 1}
            priority_score += strength_scores.get(dep.dependency_strength, 0)
            
            # Score based on team impact
            if dep.team_owner:
                team_impact = next((t for t in team_impacts if t.team_name == dep.team_owner), None)
                if team_impact:
                    impact_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
                    priority_score += impact_scores.get(team_impact.impact_level, 0)
            
            services.append((dep.service_name, priority_score))
        
        # Sort by priority score (highest first)
        services.sort(key=lambda x: x[1], reverse=True)
        
        return [service[0] for service in services]

    def _create_rollback_plan(self,
                            schema_target: str,
                            dependency_graph: DependencyGraph) -> Dict[str, Any]:
        """Create rollback plan for migration."""
        return {
            "rollback_strategy": "service_by_service",
            "rollback_order": [dep.service_name for dep in reversed(dependency_graph.direct_dependencies)],
            "prerequisites": [
                "Ensure all services have health checks",
                "Prepare previous schema versions",
                "Set up monitoring alerts"
            ],
            "rollback_triggers": [
                "Service failure rate > 5%",
                "Critical service unavailable",
                "Data corruption detected"
            ],
            "estimated_rollback_time": "30-60 minutes"
        }

    def _create_testing_strategy(self,
                               dependency_graph: DependencyGraph,
                               breaking_changes: List[BreakingChange] = None) -> Dict[str, Any]:
        """Create testing strategy for migration."""
        strategy = {
            "testing_phases": [
                "Unit testing",
                "Integration testing",
                "End-to-end testing"
            ],
            "test_environments": ["staging", "pre-production"],
            "critical_test_cases": []
        }
        
        if breaking_changes:
            strategy["critical_test_cases"].extend([
                "Backward compatibility validation",
                "Breaking change impact verification",
                "Migration data integrity check"
            ])
        
        # Add service-specific testing
        for dep in dependency_graph.direct_dependencies:
            if dep.dependency_strength in ["critical", "strong"]:
                strategy["critical_test_cases"].append(f"Service {dep.service_name} functionality validation")
        
        return strategy

    def _create_communication_plan(self,
                                 team_impacts: List[TeamImpact],
                                 cross_system_impact: CrossSystemImpact) -> Dict[str, Any]:
        """Create communication plan for migration."""
        plan = {
            "stakeholders": [],
            "notification_timeline": {},
            "communication_channels": [],
            "escalation_procedures": []
        }
        
        # Add team stakeholders
        for team_impact in team_impacts:
            plan["stakeholders"].append({
                "team": team_impact.team_name,
                "contact_priority": team_impact.contact_priority,
                "notification_requirements": team_impact.required_actions
            })
        
        # Add notification timeline
        plan["notification_timeline"] = {
            "initial_notification": "48 hours before migration",
            "pre_migration_reminder": "24 hours before migration",
            "migration_start": "At migration start",
            "progress_updates": "Every 30 minutes during migration",
            "completion_notification": "At migration completion"
        }
        
        # Communication channels based on impact
        if any(t.impact_level in ["critical", "high"] for t in team_impacts):
            plan["communication_channels"].extend(["slack", "email", "teams"])
        else:
            plan["communication_channels"].extend(["email", "slack"])
        
        return plan

    def _create_migration_timeline(self,
                                 phases: List[Dict[str, Any]],
                                 team_impacts: List[TeamImpact]) -> Dict[str, str]:
        """Create migration timeline."""
        timeline = {}
        
        # Calculate total duration
        total_hours = 0
        for phase in phases:
            duration_str = phase.get("duration", "1 hour")
            # Extract hours from duration string (simple parsing)
            if "hour" in duration_str:
                hours = duration_str.split("-")[0].strip()
                try:
                    total_hours += int(hours)
                except ValueError:
                    total_hours += 1
        
        timeline["preparation_time"] = "1-2 days"
        timeline["migration_window"] = f"{total_hours} hours"
        timeline["testing_time"] = "4-8 hours"
        timeline["rollback_window"] = "1 hour"
        
        # Adjust for high-impact teams
        high_impact_teams = len([t for t in team_impacts if t.impact_level in ["critical", "high"]])
        if high_impact_teams > 0:
            timeline["coordination_time"] = "2-4 hours"
        
        return timeline

    def _create_risk_assessment(self,
                              dependency_graph: DependencyGraph,
                              breaking_changes: List[BreakingChange] = None,
                              cross_system_impact: CrossSystemImpact = None) -> Dict[str, Any]:
        """Create risk assessment for migration."""
        risks = []
        
        # Dependency-based risks
        critical_deps = len([d for d in dependency_graph.direct_dependencies if d.dependency_strength == "critical"])
        if critical_deps > 0:
            risks.append({
                "risk": "Critical service disruption",
                "probability": "medium",
                "impact": "high",
                "mitigation": "Prepare immediate rollback plan"
            })
        
        # Breaking change risks
        if breaking_changes:
            risks.append({
                "risk": "Compatibility issues",
                "probability": "high",
                "impact": "medium",
                "mitigation": "Comprehensive testing and staged rollout"
            })
        
        # Cross-system risks
        if cross_system_impact and len(cross_system_impact.affected_systems) > 2:
            risks.append({
                "risk": "Cross-system coordination failure",
                "probability": "medium",
                "impact": "high",
                "mitigation": "Multi-system communication plan"
            })
        
        return {
            "overall_risk_level": self._calculate_overall_risk_level(risks),
            "identified_risks": risks,
            "risk_mitigation_plan": "Implement all identified mitigations before proceeding"
        }

    def _calculate_overall_risk_level(self, risks: List[Dict[str, Any]]) -> str:
        """Calculate overall risk level."""
        if not risks:
            return "low"
        
        # Check for high impact risks
        high_impact_risks = [r for r in risks if r.get("impact") == "high"]
        if high_impact_risks:
            return "high"
        
        # Check for medium impact with high probability
        medium_high_prob_risks = [
            r for r in risks 
            if r.get("impact") == "medium" and r.get("probability") == "high"
        ]
        if len(medium_high_prob_risks) > 1:
            return "medium"
        
        return "low"

    def _save_migration_plan(self, change_id: str, plan: MigrationPlan) -> None:
        """Save migration plan to storage."""
        try:
            # Load existing plans
            try:
                with open(self.migration_plans_file, 'r') as f:
                    plans = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                plans = {}
            
            # Save new plan
            plans[change_id] = asdict(plan)
            
            with open(self.migration_plans_file, 'w') as f:
                json.dump(plans, f, indent=2)
            
            logger.info(f"Saved migration plan for change {change_id}")
            
        except Exception as e:
            logger.error(f"Failed to save migration plan: {e}")


def main():
    """Main entry point for dependency impact analyzer testing."""
    parser = argparse.ArgumentParser(description="Dependency Impact Analyzer")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Register dependency
    register_parser = subparsers.add_parser("register-dependency", help="Register service dependency")
    register_parser.add_argument("--schema", required=True, help="Schema target")
    register_parser.add_argument("--service", required=True, help="Service name")
    register_parser.add_argument("--repository", required=True, help="Service repository")
    register_parser.add_argument("--type", default="direct", choices=["direct", "transitive", "optional"], help="Dependency type")
    register_parser.add_argument("--usage", default="consumer", choices=["consumer", "producer", "both"], help="Usage pattern")
    register_parser.add_argument("--strength", default="medium", choices=["weak", "medium", "strong", "critical"], help="Dependency strength")
    register_parser.add_argument("--team", help="Team owner")
    
    # Register service
    service_parser = subparsers.add_parser("register-service", help="Register service")
    service_parser.add_argument("--name", required=True, help="Service name")
    service_parser.add_argument("--info-file", required=True, help="JSON file with service info")
    
    # Analyze dependencies
    analyze_parser = subparsers.add_parser("analyze", help="Analyze dependency graph")
    analyze_parser.add_argument("--schema", required=True, help="Schema target to analyze")
    
    # Identify affected services
    affected_parser = subparsers.add_parser("affected-services", help="Identify affected services")
    affected_parser.add_argument("--schema", required=True, help="Schema target")
    affected_parser.add_argument("--breaking-changes", help="JSON file with breaking changes")
    
    # Team impact analysis
    team_parser = subparsers.add_parser("team-impacts", help="Analyze team impacts")
    team_parser.add_argument("--schema", required=True, help="Schema target")
    team_parser.add_argument("--breaking-changes", help="JSON file with breaking changes")
    
    # Generate migration plan
    migration_parser = subparsers.add_parser("migration-plan", help="Generate migration plan")
    migration_parser.add_argument("--change-id", required=True, help="Change ID")
    migration_parser.add_argument("--schema", required=True, help="Schema target")
    migration_parser.add_argument("--breaking-changes", help="JSON file with breaking changes")
    migration_parser.add_argument("--output", help="Output file for migration plan")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        analyzer = DependencyImpactAnalyzer(
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "register-dependency":
            dependency = ServiceDependency(
                service_name=args.service,
                service_repository=args.repository,
                dependency_type=args.type,
                usage_pattern=args.usage,
                dependency_strength=args.strength,
                team_owner=args.team
            )
            
            analyzer.register_service_dependency(args.schema, dependency)
            print(f"✅ Registered dependency: {args.service} -> {args.schema}")
        
        elif args.command == "register-service":
            with open(args.info_file, 'r') as f:
                service_info = json.load(f)
            
            analyzer.register_service(args.name, service_info)
            print(f"✅ Registered service: {args.name}")
        
        elif args.command == "analyze":
            graph = analyzer.analyze_dependency_graph(args.schema)
            
            print(f"🔍 Dependency Analysis for {args.schema}")
            print(f"   Direct dependencies: {len(graph.direct_dependencies)}")
            print(f"   Transitive dependencies: {len(graph.transitive_dependencies)}")
            print(f"   Total affected services: {graph.analysis_metadata['total_affected_services']}")
            print(f"   Critical dependencies: {graph.analysis_metadata['critical_dependencies']}")
            print(f"   Teams affected: {graph.analysis_metadata['teams_affected']}")
            print(f"   Complexity score: {graph.analysis_metadata['complexity_score']}")
            
            if graph.direct_dependencies:
                print(f"\n   Direct dependencies:")
                for dep in graph.direct_dependencies:
                    print(f"     {dep.service_name} ({dep.dependency_strength}) - Team: {dep.team_owner or 'Unknown'}")
        
        elif args.command == "affected-services":
            breaking_changes = []
            if args.breaking_changes:
                with open(args.breaking_changes, 'r') as f:
                    changes_data = json.load(f)
                breaking_changes = [BreakingChange(**change) for change in changes_data]
            
            affected_services = analyzer.identify_affected_services(args.schema, breaking_changes)
            
            print(f"🎯 Affected Services for {args.schema}")
            for service in affected_services:
                print(f"   {service['service_name']}: {service['impact_level']} impact")
                print(f"     Team: {service.get('team_owner', 'Unknown')}")
                print(f"     Migration required: {service.get('migration_required', False)}")
                print()
        
        elif args.command == "team-impacts":
            breaking_changes = []
            if args.breaking_changes:
                with open(args.breaking_changes, 'r') as f:
                    changes_data = json.load(f)
                breaking_changes = [BreakingChange(**change) for change in changes_data]
            
            team_impacts = analyzer.analyze_team_impacts(args.schema, breaking_changes)
            
            print(f"👥 Team Impacts for {args.schema}")
            for team_impact in team_impacts:
                print(f"   Team {team_impact.team_name}: {team_impact.impact_level} impact")
                print(f"     Affected services: {len(team_impact.affected_services)}")
                print(f"     Required actions: {len(team_impact.required_actions)}")
                print(f"     Contact priority: {team_impact.contact_priority}")
                if team_impact.mitigation_strategies:
                    print(f"     Mitigation strategies:")
                    for strategy in team_impact.mitigation_strategies:
                        print(f"       - {strategy}")
                print()
        
        elif args.command == "migration-plan":
            breaking_changes = []
            if args.breaking_changes:
                with open(args.breaking_changes, 'r') as f:
                    changes_data = json.load(f)
                breaking_changes = [BreakingChange(**change) for change in changes_data]
            
            plan = analyzer.generate_migration_plan(args.change_id, args.schema, breaking_changes)
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(asdict(plan), f, indent=2)
                print(f"📋 Migration plan saved to {args.output}")
            else:
                print(f"📋 Migration Plan for {args.schema}")
                print(f"   Strategy: {plan.migration_strategy}")
                print(f"   Phases: {len(plan.phases)}")
                print(f"   Risk level: {plan.risk_assessment.get('overall_risk_level', 'unknown')}")
                
                for phase in plan.phases:
                    print(f"\n   Phase {phase['phase']}: {phase['name']}")
                    print(f"     Services: {len(phase['services'])}")
                    print(f"     Duration: {phase['duration']}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
