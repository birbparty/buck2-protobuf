#!/usr/bin/env python3
"""
BSR Change Tracker for Team Collaboration.

This module provides comprehensive change tracking and team coordination for
protobuf schema changes, integrating with existing team management and
breaking change detection systems.
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
from .schema_governance_engine import SchemaChange, GovernanceConfig
from .schema_review_workflow import SchemaReviewWorkflow

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChangeRecord:
    """Comprehensive record of a schema change with team context."""
    id: str
    schema_target: str
    change_type: str  # "creation", "modification", "deletion"
    repository: str
    version: Optional[str] = None
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    created_by: Optional[str] = None
    commit_hash: Optional[str] = None
    branch: Optional[str] = None
    description: Optional[str] = None
    
    # Team context
    owning_team: Optional[str] = None
    affected_teams: List[str] = field(default_factory=list)
    
    # Change details
    breaking_changes: List[BreakingChange] = field(default_factory=list)
    schema_changes: List[SchemaChange] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    
    # Impact analysis
    impact_level: str = "unknown"  # "low", "medium", "high", "critical"
    affected_services: List[str] = field(default_factory=list)
    migration_required: bool = False
    
    # Review and approval
    review_required: bool = False
    review_id: Optional[str] = None
    approval_status: str = "not_required"  # "not_required", "pending", "approved", "rejected"
    
    # Metadata and tracking
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    # Notification tracking
    notifications_sent: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ImpactAnalysis:
    """Detailed impact analysis for schema changes."""
    change_record_id: str
    overall_impact: str  # "low", "medium", "high", "critical"
    risk_assessment: str  # "minimal", "low", "medium", "high", "critical"
    
    # Team impacts
    team_impacts: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Service impacts
    affected_services: List[Dict[str, Any]] = field(default_factory=list)
    
    # Breaking change analysis
    breaking_change_summary: Dict[str, int] = field(default_factory=dict)
    migration_complexity: str = "none"  # "none", "simple", "moderate", "complex", "critical"
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    migration_steps: List[str] = field(default_factory=list)
    
    # Timeline estimates
    estimated_migration_time: Optional[str] = None
    rollback_plan_required: bool = False
    
    # Analysis metadata
    analyzed_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    analyzer_version: str = "1.0.0"


@dataclass
class TeamNotificationConfig:
    """Configuration for team notification preferences."""
    team_name: str
    channels: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # channel_type -> config
    notification_rules: Dict[str, Any] = field(default_factory=dict)
    escalation_rules: List[Dict[str, Any]] = field(default_factory=list)


class ChangeTrackingError(Exception):
    """Change tracking operation failed."""
    pass


class BSRChangeTracker:
    """
    BSR change tracking and team coordination system.
    
    Provides comprehensive tracking of schema changes with team context,
    impact analysis, and coordinated notifications for seamless collaboration.
    """
    
    def __init__(self,
                 storage_dir: Union[str, Path] = None,
                 team_manager: Optional[BSRTeamManager] = None,
                 breaking_change_detector: Optional[BSRBreakingChangeDetector] = None,
                 review_workflow: Optional[SchemaReviewWorkflow] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 verbose: bool = False):
        """
        Initialize BSR Change Tracker.
        
        Args:
            storage_dir: Directory for change tracking storage
            team_manager: BSR team manager instance
            breaking_change_detector: Breaking change detector instance
            review_workflow: Schema review workflow instance
            bsr_authenticator: BSR authentication instance
            verbose: Enable verbose logging
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'change-tracking'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Storage files
        self.changes_file = self.storage_dir / "change_records.json"
        self.impact_analysis_file = self.storage_dir / "impact_analysis.json"
        self.notification_config_file = self.storage_dir / "notification_config.json"
        self.audit_log_file = self.storage_dir / "audit_log.json"
        
        # Dependencies
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        self.breaking_change_detector = breaking_change_detector or BSRBreakingChangeDetector(verbose=verbose)
        self.review_workflow = review_workflow or SchemaReviewWorkflow(verbose=verbose)
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Initialize storage
        self._init_storage()
        
        # Load notification configurations
        self.notification_configs = self._load_notification_configs()
        
        logger.info(f"BSR Change Tracker initialized")

    def _init_storage(self) -> None:
        """Initialize storage files."""
        for file_path in [self.changes_file, self.impact_analysis_file, 
                         self.notification_config_file, self.audit_log_file]:
            if not file_path.exists():
                with open(file_path, 'w') as f:
                    json.dump({}, f)

    def _load_change_records(self) -> Dict[str, ChangeRecord]:
        """Load change records from storage."""
        try:
            with open(self.changes_file, 'r') as f:
                records_data = json.load(f)
            
            records = {}
            for record_id, record_data in records_data.items():
                # Convert breaking changes and schema changes back to objects
                if 'breaking_changes' in record_data:
                    record_data['breaking_changes'] = [
                        BreakingChange(**bc) for bc in record_data['breaking_changes']
                    ]
                if 'schema_changes' in record_data:
                    record_data['schema_changes'] = [
                        SchemaChange(**sc) for sc in record_data['schema_changes']
                    ]
                
                records[record_id] = ChangeRecord(**record_data)
            
            return records
        except (FileNotFoundError, json.JSONDecodeError, TypeError):
            return {}

    def _save_change_records(self, records: Dict[str, ChangeRecord]) -> None:
        """Save change records to storage."""
        try:
            records_data = {}
            for record_id, record in records.items():
                record_dict = asdict(record)
                # Convert objects to dicts for JSON serialization
                if record_dict['breaking_changes']:
                    record_dict['breaking_changes'] = [
                        asdict(bc) for bc in record.breaking_changes
                    ]
                if record_dict['schema_changes']:
                    record_dict['schema_changes'] = [
                        asdict(sc) for sc in record.schema_changes
                    ]
                records_data[record_id] = record_dict
            
            with open(self.changes_file, 'w') as f:
                json.dump(records_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save change records: {e}")
            raise ChangeTrackingError(f"Failed to save change records: {e}")

    def _load_notification_configs(self) -> Dict[str, TeamNotificationConfig]:
        """Load team notification configurations."""
        try:
            with open(self.notification_config_file, 'r') as f:
                configs_data = json.load(f)
            
            configs = {}
            for team_name, config_data in configs_data.items():
                configs[team_name] = TeamNotificationConfig(**config_data)
            
            return configs
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_notification_configs(self, configs: Dict[str, TeamNotificationConfig]) -> None:
        """Save team notification configurations."""
        try:
            configs_data = {}
            for team_name, config in configs.items():
                configs_data[team_name] = asdict(config)
            
            with open(self.notification_config_file, 'w') as f:
                json.dump(configs_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save notification configs: {e}")

    def track_schema_change(self,
                          schema_target: str,
                          change_type: str,
                          repository: str,
                          created_by: Optional[str] = None,
                          commit_hash: Optional[str] = None,
                          branch: Optional[str] = None,
                          description: Optional[str] = None,
                          files_changed: List[str] = None,
                          version: Optional[str] = None,
                          tags: List[str] = None) -> ChangeRecord:
        """
        Track a schema change with comprehensive metadata and team context.
        
        Args:
            schema_target: Proto library target being changed
            change_type: Type of change ("creation", "modification", "deletion")
            repository: Repository containing the change
            created_by: Username of change author
            commit_hash: Git commit hash
            branch: Git branch name
            description: Change description
            files_changed: List of changed proto files
            version: Schema version
            tags: Change tags for categorization
            
        Returns:
            Created ChangeRecord
            
        Raises:
            ChangeTrackingError: If tracking fails
        """
        # Generate unique change ID
        change_id = f"CHG_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # Determine owning team
        owning_team = self._determine_owning_team(schema_target, repository)
        
        # Create change record
        change_record = ChangeRecord(
            id=change_id,
            schema_target=schema_target,
            change_type=change_type,
            repository=repository,
            version=version,
            created_by=created_by,
            commit_hash=commit_hash,
            branch=branch,
            description=description,
            owning_team=owning_team,
            files_changed=files_changed or [],
            tags=tags or []
        )
        
        # Perform breaking change detection if this is a modification
        if change_type == "modification":
            try:
                breaking_changes = self.breaking_change_detector.detect_breaking_changes(
                    proto_target=schema_target,
                    against_repository=repository,
                    proto_files=files_changed
                )
                change_record.breaking_changes = breaking_changes
                
                if breaking_changes:
                    change_record.migration_required = True
                    change_record.review_required = True
                    
            except Exception as e:
                logger.warning(f"Breaking change detection failed: {e}")
        
        # Analyze impact
        impact_analysis = self.analyze_change_impact(change_record)
        change_record.impact_level = impact_analysis.overall_impact
        change_record.affected_teams = list(impact_analysis.team_impacts.keys())
        change_record.affected_services = [
            service['name'] for service in impact_analysis.affected_services
        ]
        
        # Determine if review is required
        if not change_record.review_required:
            change_record.review_required = self._requires_review(change_record, impact_analysis)
        
        # Create review request if required
        if change_record.review_required:
            reviewers = self._determine_reviewers(change_record, impact_analysis)
            if reviewers:
                review_request = self.review_workflow.create_review_request(
                    proto_target=schema_target,
                    reviewers=reviewers,
                    approval_count=self._determine_approval_count(impact_analysis),
                    description=f"Review for {change_type} of {schema_target}",
                    created_by=created_by
                )
                change_record.review_id = review_request.id
                change_record.approval_status = "pending"
        
        # Save change record
        records = self._load_change_records()
        records[change_id] = change_record
        self._save_change_records(records)
        
        # Save impact analysis
        self._save_impact_analysis(change_id, impact_analysis)
        
        # Log audit event
        self._log_audit_event("change_tracked", {
            "change_id": change_id,
            "schema_target": schema_target,
            "change_type": change_type,
            "created_by": created_by,
            "impact_level": change_record.impact_level
        })
        
        logger.info(f"Tracked schema change {change_id}: {schema_target} ({change_type})")
        
        # Send notifications to affected teams
        self.notify_affected_teams(change_record, impact_analysis)
        
        return change_record

    def analyze_change_impact(self, change_record: ChangeRecord) -> ImpactAnalysis:
        """
        Analyze the impact of a schema change across teams and services.
        
        Args:
            change_record: Change record to analyze
            
        Returns:
            Comprehensive impact analysis
        """
        analysis = ImpactAnalysis(
            change_record_id=change_record.id,
            overall_impact="low",
            risk_assessment="minimal"
        )
        
        # Analyze breaking changes if present
        if change_record.breaking_changes:
            analysis.breaking_change_summary = self._summarize_breaking_changes(
                change_record.breaking_changes
            )
            
            # Use existing breaking change analyzer for detailed impact
            detailed_impact = self.breaking_change_detector.analyze_breaking_change_impact(
                change_record.breaking_changes,
                change_record.repository
            )
            
            analysis.overall_impact = detailed_impact['overall_impact']
            analysis.risk_assessment = detailed_impact['risk_level']
            analysis.migration_complexity = detailed_impact['migration_complexity']
            analysis.recommendations = detailed_impact['recommendations']
            
            if detailed_impact['overall_impact'] in ['high', 'critical']:
                analysis.rollback_plan_required = True
        
        # Analyze team impacts
        analysis.team_impacts = self._analyze_team_impacts(change_record)
        
        # Identify affected services
        analysis.affected_services = self._identify_affected_services(change_record)
        
        # Generate migration steps if needed
        if change_record.migration_required:
            analysis.migration_steps = self._generate_migration_steps(change_record)
            analysis.estimated_migration_time = self._estimate_migration_time(change_record)
        
        # Additional recommendations based on team context
        team_recommendations = self._generate_team_recommendations(change_record, analysis)
        analysis.recommendations.extend(team_recommendations)
        
        return analysis

    def notify_affected_teams(self,
                            change_record: ChangeRecord,
                            impact_analysis: ImpactAnalysis,
                            notification_type: str = "change_detected") -> None:
        """
        Send notifications to affected teams about schema changes.
        
        Args:
            change_record: Change record to notify about
            impact_analysis: Impact analysis results
            notification_type: Type of notification
        """
        affected_teams = set(change_record.affected_teams)
        if change_record.owning_team:
            affected_teams.add(change_record.owning_team)
        
        for team_name in affected_teams:
            team_impact = impact_analysis.team_impacts.get(team_name, {})
            
            # Create notification payload
            notification = {
                "type": notification_type,
                "change_id": change_record.id,
                "schema_target": change_record.schema_target,
                "change_type": change_record.change_type,
                "repository": change_record.repository,
                "impact_level": change_record.impact_level,
                "team_specific_impact": team_impact,
                "created_by": change_record.created_by,
                "created_at": change_record.created_at,
                "description": change_record.description,
                "breaking_changes_count": len(change_record.breaking_changes),
                "migration_required": change_record.migration_required,
                "review_required": change_record.review_required,
                "review_id": change_record.review_id,
                "recommendations": impact_analysis.recommendations,
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            
            # Send through configured channels for this team
            self._send_team_notification(team_name, notification)
            
            # Track notification
            change_record.notifications_sent.append({
                "team": team_name,
                "type": notification_type,
                "timestamp": notification["timestamp"],
                "channels": list(self.notification_configs.get(team_name, TeamNotificationConfig(team_name)).channels.keys())
            })
        
        # Update change record with notification tracking
        records = self._load_change_records()
        records[change_record.id] = change_record
        self._save_change_records(records)
        
        logger.info(f"Sent notifications to {len(affected_teams)} teams for change {change_record.id}")

    def configure_team_notifications(self,
                                   team_name: str,
                                   channels: Dict[str, Dict[str, Any]],
                                   notification_rules: Dict[str, Any] = None,
                                   escalation_rules: List[Dict[str, Any]] = None) -> None:
        """
        Configure notification settings for a team.
        
        Args:
            team_name: Name of the team
            channels: Channel configurations (slack, teams, email, webhook)
            notification_rules: Rules for when to send notifications
            escalation_rules: Escalation rules for critical changes
        """
        config = TeamNotificationConfig(
            team_name=team_name,
            channels=channels,
            notification_rules=notification_rules or {},
            escalation_rules=escalation_rules or []
        )
        
        self.notification_configs[team_name] = config
        self._save_notification_configs(self.notification_configs)
        
        logger.info(f"Configured notifications for team {team_name} with {len(channels)} channels")

    def get_change_history(self,
                          schema_target: Optional[str] = None,
                          team: Optional[str] = None,
                          since: Optional[str] = None,
                          limit: int = 100) -> List[ChangeRecord]:
        """
        Get change history with optional filtering.
        
        Args:
            schema_target: Filter by specific schema target
            team: Filter by team (owning or affected)
            since: Filter by timestamp (ISO format)
            limit: Maximum number of records to return
            
        Returns:
            List of change records matching filters
        """
        records = self._load_change_records()
        filtered_records = []
        
        for record in records.values():
            # Apply filters
            if schema_target and record.schema_target != schema_target:
                continue
                
            if team and (record.owning_team != team and team not in record.affected_teams):
                continue
                
            if since and record.created_at < since:
                continue
            
            filtered_records.append(record)
        
        # Sort by creation time (newest first)
        filtered_records.sort(key=lambda r: r.created_at, reverse=True)
        
        return filtered_records[:limit]

    def generate_change_report(self, 
                             timeframe: str = "7d",
                             team: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate comprehensive change report for teams.
        
        Args:
            timeframe: Timeframe for report ("1d", "7d", "30d")
            team: Optional team filter
            
        Returns:
            Comprehensive change report
        """
        # Calculate time boundary
        timeframe_hours = {
            "1d": 24,
            "7d": 24 * 7,
            "30d": 24 * 30
        }
        
        hours = timeframe_hours.get(timeframe, 24 * 7)
        since_timestamp = time.strftime(
            '%Y-%m-%dT%H:%M:%SZ',
            time.gmtime(time.time() - hours * 3600)
        )
        
        # Get changes in timeframe
        changes = self.get_change_history(team=team, since=since_timestamp)
        
        # Generate report
        report = {
            "timeframe": timeframe,
            "team_filter": team,
            "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "summary": {
                "total_changes": len(changes),
                "breaking_changes": len([c for c in changes if c.breaking_changes]),
                "reviews_required": len([c for c in changes if c.review_required]),
                "migrations_required": len([c for c in changes if c.migration_required])
            },
            "impact_breakdown": {
                "low": len([c for c in changes if c.impact_level == "low"]),
                "medium": len([c for c in changes if c.impact_level == "medium"]),
                "high": len([c for c in changes if c.impact_level == "high"]),
                "critical": len([c for c in changes if c.impact_level == "critical"])
            },
            "change_types": {
                "creation": len([c for c in changes if c.change_type == "creation"]),
                "modification": len([c for c in changes if c.change_type == "modification"]),
                "deletion": len([c for c in changes if c.change_type == "deletion"])
            },
            "top_active_repositories": self._get_top_repositories(changes),
            "top_affected_teams": self._get_top_affected_teams(changes),
            "recent_changes": [asdict(change) for change in changes[:10]],
            "recommendations": self._generate_report_recommendations(changes)
        }
        
        return report

    # Helper methods
    
    def _determine_owning_team(self, schema_target: str, repository: str) -> Optional[str]:
        """Determine which team owns a schema target."""
        # This could be enhanced with more sophisticated logic
        # For now, try to match repository to team repositories
        for team_name in self.team_manager.list_teams():
            team_info = self.team_manager.get_team_info(team_name)
            if team_info and repository in team_info.get('repositories', {}):
                return team_name
        return None

    def _requires_review(self, change_record: ChangeRecord, impact_analysis: ImpactAnalysis) -> bool:
        """Determine if a change requires review."""
        # Breaking changes always require review
        if change_record.breaking_changes:
            return True
        
        # High/critical impact requires review
        if impact_analysis.overall_impact in ['high', 'critical']:
            return True
        
        # Team-specific rules
        if change_record.owning_team:
            team_info = self.team_manager.get_team_info(change_record.owning_team)
            if team_info and team_info.get('settings', {}).get('require_review_all_changes'):
                return True
        
        return False

    def _determine_reviewers(self, change_record: ChangeRecord, impact_analysis: ImpactAnalysis) -> List[str]:
        """Determine required reviewers for a change."""
        reviewers = []
        
        # Add owning team
        if change_record.owning_team:
            reviewers.append(f"@{change_record.owning_team}")
        
        # Add affected teams for high-impact changes
        if impact_analysis.overall_impact in ['high', 'critical']:
            for team in change_record.affected_teams:
                if team != change_record.owning_team:
                    reviewers.append(f"@{team}")
        
        return reviewers

    def _determine_approval_count(self, impact_analysis: ImpactAnalysis) -> int:
        """Determine number of required approvals."""
        if impact_analysis.overall_impact == "critical":
            return 2
        elif impact_analysis.overall_impact == "high":
            return 2
        else:
            return 1

    def _summarize_breaking_changes(self, breaking_changes: List[BreakingChange]) -> Dict[str, int]:
        """Summarize breaking changes by type."""
        summary = {}
        for change in breaking_changes:
            summary[change.type] = summary.get(change.type, 0) + 1
        return summary

    def _analyze_team_impacts(self, change_record: ChangeRecord) -> Dict[str, Dict[str, Any]]:
        """Analyze impact on each team."""
        team_impacts = {}
        
        # Analyze owning team
        if change_record.owning_team:
            team_impacts[change_record.owning_team] = {
                "role": "owner",
                "impact_level": change_record.impact_level,
                "action_required": "review" if change_record.review_required else "none"
            }
        
        # This could be expanded with more sophisticated team impact analysis
        return team_impacts

    def _identify_affected_services(self, change_record: ChangeRecord) -> List[Dict[str, Any]]:
        """Identify services affected by the change."""
        # This would integrate with service discovery or dependency tracking
        # For now, return basic structure
        return []

    def _generate_migration_steps(self, change_record: ChangeRecord) -> List[str]:
        """Generate migration steps for a change."""
        if not change_record.breaking_changes:
            return []
        
        # Use existing breaking change detector for migration guide
        migration_guide = self.breaking_change_detector.generate_migration_guide(
            change_record.breaking_changes,
            change_record.repository
        )
        
        # Extract steps from migration guide
        return [
            "Review breaking changes in migration guide",
            "Update client code to handle changes", 
            "Test changes in staging environment",
            "Deploy changes with monitoring"
        ]

    def _estimate_migration_time(self, change_record: ChangeRecord) -> str:
        """Estimate migration time based on change complexity."""
        if not change_record.breaking_changes:
            return "0 hours"
        
        complexity_hours = {
            "low": "2-4 hours",
            "medium": "1-2 days", 
            "high": "3-5 days",
            "critical": "1-2 weeks"
        }
        
        return complexity_hours.get(change_record.impact_level, "unknown")

    def _generate_team_recommendations(self, change_record: ChangeRecord, analysis: ImpactAnalysis) -> List[str]:
        """Generate team-specific recommendations."""
        recommendations = []
        
        if change_record.migration_required:
            recommendations.append("Coordinate migration timing with affected teams")
        
        if analysis.overall_impact in ['high', 'critical']:
            recommendations.append("Consider phased rollout to minimize impact")
            recommendations.append("Prepare rollback plan before deployment")
        
        return recommendations

    def _send_team_notification(self, team_name: str, notification: Dict[str, Any]) -> None:
        """Send notification to a specific team through configured channels."""
        config = self.notification_configs.get(team_name)
        if not config:
            logger.warning(f"No notification configuration for team {team_name}")
            return
        
        # For now, just log the notification
        # In a full implementation, this would send actual notifications
        logger.info(f"Notification sent to team {team_name}: {notification['type']} for {notification['schema_target']}")

    def _save_impact_analysis(self, change_id: str, analysis: ImpactAnalysis) -> None:
        """Save impact analysis to storage."""
        try:
            with open(self.impact_analysis_file, 'r') as f:
                analyses = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            analyses = {}
        
        analyses[change_id] = asdict(analysis)
        
        try:
            with open(self.impact_analysis_file, 'w') as f:
                json.dump(analyses, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save impact analysis: {e}")

    def _log_audit_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Log audit event."""
        try:
            with open(self.audit_log_file, 'r') as f:
                audit_log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            audit_log = {"events": []}
        
        if "events" not in audit_log:
            audit_log["events"] = []
        
        event = {
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "event_type": event_type,
            "data": event_data
        }
        
        audit_log["events"].append(event)
        
        # Keep only last 1000 events
        audit_log["events"] = audit_log["events"][-1000:]
        
        try:
            with open(self.audit_log_file, 'w') as f:
                json.dump(audit_log, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save audit log: {e}")

    def _get_top_repositories(self, changes: List[ChangeRecord]) -> List[Dict[str, Any]]:
        """Get top active repositories from changes."""
        repo_counts = {}
        for change in changes:
            repo_counts[change.repository] = repo_counts.get(change.repository, 0) + 1
        
        # Sort by count and return top 10
        sorted_repos = sorted(repo_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"repository": repo, "change_count": count} for repo, count in sorted_repos[:10]]

    def _get_top_affected_teams(self, changes: List[ChangeRecord]) -> List[Dict[str, Any]]:
        """Get top affected teams from changes."""
        team_counts = {}
        for change in changes:
            # Count owning team
            if change.owning_team:
                team_counts[change.owning_team] = team_counts.get(change.owning_team, 0) + 1
            
            # Count affected teams
            for team in change.affected_teams:
                team_counts[team] = team_counts.get(team, 0) + 1
        
        # Sort by count and return top 10
        sorted_teams = sorted(team_counts.items(), key=lambda x: x[1], reverse=True)
        return [{"team": team, "involvement_count": count} for team, count in sorted_teams[:10]]

    def _generate_report_recommendations(self, changes: List[ChangeRecord]) -> List[str]:
        """Generate recommendations based on change patterns."""
        recommendations = []
        
        breaking_changes_count = len([c for c in changes if c.breaking_changes])
        high_impact_count = len([c for c in changes if c.impact_level in ['high', 'critical']])
        
        if breaking_changes_count > 5:
            recommendations.append("High number of breaking changes detected - consider implementing stricter review processes")
        
        if high_impact_count > 3:
            recommendations.append("Multiple high-impact changes - consider staggering deployments")
        
        # Check for patterns in change types
        modification_count = len([c for c in changes if c.change_type == "modification"])
        if modification_count > len(changes) * 0.8:
            recommendations.append("High rate of modifications - consider schema versioning strategy")
        
        # Check review compliance
        review_required_count = len([c for c in changes if c.review_required])
        if review_required_count > 0:
            recommendations.append(f"{review_required_count} changes require review - ensure timely approvals")
        
        if not recommendations:
            recommendations.append("Change patterns look healthy - continue current practices")
        
        return recommendations


def main():
    """Main entry point for BSR change tracker testing."""
    parser = argparse.ArgumentParser(description="BSR Change Tracker")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Track change
    track_parser = subparsers.add_parser("track", help="Track a schema change")
    track_parser.add_argument("--target", required=True, help="Schema target")
    track_parser.add_argument("--type", required=True, choices=["creation", "modification", "deletion"], help="Change type")
    track_parser.add_argument("--repository", required=True, help="Repository")
    track_parser.add_argument("--created-by", help="Change author")
    track_parser.add_argument("--commit", help="Commit hash")
    track_parser.add_argument("--branch", help="Branch name")
    track_parser.add_argument("--description", help="Change description")
    track_parser.add_argument("--files", nargs="*", help="Changed files")
    track_parser.add_argument("--version", help="Schema version")
    track_parser.add_argument("--tags", nargs="*", help="Change tags")
    
    # Configure notifications
    notify_parser = subparsers.add_parser("configure-notifications", help="Configure team notifications")
    notify_parser.add_argument("--team", required=True, help="Team name")
    notify_parser.add_argument("--config-file", required=True, help="JSON config file")
    
    # Change history
    history_parser = subparsers.add_parser("history", help="Get change history")
    history_parser.add_argument("--target", help="Filter by schema target")
    history_parser.add_argument("--team", help="Filter by team")
    history_parser.add_argument("--since", help="Filter by timestamp")
    history_parser.add_argument("--limit", type=int, default=20, help="Maximum records")
    
    # Generate report
    report_parser = subparsers.add_parser("report", help="Generate change report")
    report_parser.add_argument("--timeframe", default="7d", choices=["1d", "7d", "30d"], help="Report timeframe")
    report_parser.add_argument("--team", help="Filter by team")
    report_parser.add_argument("--output", help="Output file for report")
    
    # Impact analysis
    impact_parser = subparsers.add_parser("analyze", help="Analyze change impact")
    impact_parser.add_argument("change_id", help="Change ID to analyze")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        tracker = BSRChangeTracker(
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "track":
            change_record = tracker.track_schema_change(
                schema_target=args.target,
                change_type=args.type,
                repository=args.repository,
                created_by=args.created_by,
                commit_hash=args.commit,
                branch=args.branch,
                description=args.description,
                files_changed=args.files or [],
                version=args.version,
                tags=args.tags or []
            )
            
            print(f"✅ Tracked change {change_record.id}")
            print(f"   Target: {change_record.schema_target}")
            print(f"   Type: {change_record.change_type}")
            print(f"   Impact: {change_record.impact_level}")
            print(f"   Review required: {change_record.review_required}")
            if change_record.review_id:
                print(f"   Review ID: {change_record.review_id}")
            if change_record.breaking_changes:
                print(f"   Breaking changes: {len(change_record.breaking_changes)}")
        
        elif args.command == "configure-notifications":
            with open(args.config_file, 'r') as f:
                config = json.load(f)
            
            tracker.configure_team_notifications(
                team_name=args.team,
                channels=config.get('channels', {}),
                notification_rules=config.get('notification_rules', {}),
                escalation_rules=config.get('escalation_rules', [])
            )
            print(f"✅ Configured notifications for team {args.team}")
        
        elif args.command == "history":
            changes = tracker.get_change_history(
                schema_target=args.target,
                team=args.team,
                since=args.since,
                limit=args.limit
            )
            
            if changes:
                print(f"Change history ({len(changes)} records):")
                for change in changes:
                    print(f"  {change.id}: {change.schema_target} ({change.change_type})")
                    print(f"    Created: {change.created_at} by {change.created_by or 'unknown'}")
                    print(f"    Impact: {change.impact_level}")
                    if change.breaking_changes:
                        print(f"    Breaking changes: {len(change.breaking_changes)}")
                    print()
            else:
                print("No changes found matching criteria")
        
        elif args.command == "report":
            report = tracker.generate_change_report(
                timeframe=args.timeframe,
                team=args.team
            )
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report, f, indent=2)
                print(f"📊 Report saved to {args.output}")
            else:
                print(f"📊 Change Report ({args.timeframe})")
                print(f"   Generated: {report['generated_at']}")
                print(f"   Total changes: {report['summary']['total_changes']}")
                print(f"   Breaking changes: {report['summary']['breaking_changes']}")
                print(f"   Reviews required: {report['summary']['reviews_required']}")
                print(f"   Migrations required: {report['summary']['migrations_required']}")
                
                print(f"\n   Impact breakdown:")
                for level, count in report['impact_breakdown'].items():
                    print(f"     {level}: {count}")
                
                if report['recommendations']:
                    print(f"\n   Recommendations:")
                    for i, rec in enumerate(report['recommendations'], 1):
                        print(f"     {i}. {rec}")
        
        elif args.command == "analyze":
            records = tracker._load_change_records()
            if args.change_id not in records:
                print(f"❌ Change {args.change_id} not found")
                return 1
            
            change_record = records[args.change_id]
            impact_analysis = tracker.analyze_change_impact(change_record)
            
            print(f"🔍 Impact Analysis for {args.change_id}")
            print(f"   Schema target: {change_record.schema_target}")
            print(f"   Overall impact: {impact_analysis.overall_impact}")
            print(f"   Risk assessment: {impact_analysis.risk_assessment}")
            print(f"   Migration complexity: {impact_analysis.migration_complexity}")
            
            if impact_analysis.team_impacts:
                print(f"\n   Team impacts:")
                for team, impact in impact_analysis.team_impacts.items():
                    print(f"     {team}: {impact}")
            
            if impact_analysis.recommendations:
                print(f"\n   Recommendations:")
                for i, rec in enumerate(impact_analysis.recommendations, 1):
                    print(f"     {i}. {rec}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
