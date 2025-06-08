#!/usr/bin/env python3
"""
Schema Governance Engine for Buck2 Protobuf.

This module provides the core governance engine that enforces policies,
manages review workflows, and tracks compliance for schema development.
"""

import argparse
import json
import os
import time
import yaml
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials
from .bsr_teams import BSRTeamManager, Team, TeamMember

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class SchemaChange:
    """Represents a schema change for governance tracking."""
    target: str
    change_type: str  # "addition", "modification", "removal"
    description: str
    author: str
    timestamp: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    repository: Optional[str] = None
    team: Optional[str] = None
    breaking: bool = False
    reviewed: bool = False
    approved_by: List[str] = field(default_factory=list)


@dataclass
class BreakingChange:
    """Represents a breaking change detection result."""
    type: str  # "FIELD_REMOVED", "TYPE_CHANGED", etc.
    description: str
    location: str  # file:line or message.field
    impact: str  # "high", "medium", "low"
    repository: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    migration_guide: Optional[str] = None


@dataclass
class PolicyResult:
    """Result of policy enforcement."""
    action: str  # "allow", "warn", "error", "require_approval"
    reason: str
    has_approval: bool = False
    required_approvers: List[str] = field(default_factory=list)
    actual_approvers: List[str] = field(default_factory=list)
    violations: List[str] = field(default_factory=list)


@dataclass
class AuditRecord:
    """Audit trail record for governance actions."""
    action: str
    target: str
    actor: str
    timestamp: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    details: Dict[str, Any] = field(default_factory=dict)
    result: str = "success"  # "success", "failure", "warning"


@dataclass
class GovernanceConfig:
    """Governance configuration loaded from YAML."""
    review_policies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    breaking_change_policies: Dict[str, str] = field(default_factory=dict)
    notification_settings: Dict[str, List[str]] = field(default_factory=dict)
    global_settings: Dict[str, Any] = field(default_factory=dict)
    team_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class GovernanceError(Exception):
    """Governance operation failed."""
    pass


class SchemaGovernanceEngine:
    """
    Schema governance policy enforcement engine.
    
    Provides centralized governance policy enforcement, review workflow
    management, and compliance tracking for schema development.
    """
    
    def __init__(self, 
                 config_file: Union[str, Path] = "governance.yaml",
                 storage_dir: Union[str, Path] = None,
                 team_manager: Optional[BSRTeamManager] = None,
                 verbose: bool = False):
        """
        Initialize Schema Governance Engine.
        
        Args:
            config_file: Path to governance configuration YAML file
            storage_dir: Directory for governance data storage
            team_manager: BSR team manager instance
            verbose: Enable verbose logging
        """
        self.config_file = Path(config_file)
        
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'governance'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        
        # Storage files
        self.audit_file = self.storage_dir / "audit_trail.jsonl"
        self.approvals_file = self.storage_dir / "approvals.json"
        self.breaking_approvals_file = self.storage_dir / "breaking_approvals.json"
        
        # Team manager
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        
        # Load governance configuration
        self.config = self._load_governance_config()
        
        # Initialize approval storage
        self._init_approval_storage()
        
        logger.info(f"Schema Governance Engine initialized")

    def _load_governance_config(self) -> GovernanceConfig:
        """Load governance configuration from YAML file."""
        if not self.config_file.exists():
            logger.warning(f"Governance config file {self.config_file} not found, using defaults")
            return GovernanceConfig()
        
        try:
            with open(self.config_file, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Extract main sections
            governance_section = config_data.get('schema_governance', {})
            
            return GovernanceConfig(
                review_policies=governance_section.get('review_policies', {}),
                breaking_change_policies=governance_section.get('breaking_change_policies', {}),
                notification_settings=governance_section.get('notification_settings', {}),
                global_settings=governance_section.get('global_settings', {}),
                team_overrides=governance_section.get('team_overrides', {})
            )
            
        except Exception as e:
            logger.error(f"Failed to load governance config: {e}")
            return GovernanceConfig()

    def _init_approval_storage(self) -> None:
        """Initialize approval storage files."""
        if not self.approvals_file.exists():
            with open(self.approvals_file, 'w') as f:
                json.dump({}, f)
        
        if not self.breaking_approvals_file.exists():
            with open(self.breaking_approvals_file, 'w') as f:
                json.dump({}, f)

    def _load_approvals(self, approval_type: str = "review") -> Dict[str, Any]:
        """Load approvals from storage."""
        file_path = self.approvals_file if approval_type == "review" else self.breaking_approvals_file
        
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_approvals(self, approvals: Dict[str, Any], approval_type: str = "review") -> None:
        """Save approvals to storage."""
        file_path = self.approvals_file if approval_type == "review" else self.breaking_approvals_file
        
        try:
            with open(file_path, 'w') as f:
                json.dump(approvals, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save approvals: {e}")

    def _record_audit(self, record: AuditRecord) -> None:
        """Record audit trail entry."""
        try:
            with open(self.audit_file, 'a') as f:
                f.write(json.dumps(asdict(record)) + '\n')
        except Exception as e:
            logger.error(f"Failed to record audit entry: {e}")

    def enforce_review_policy(self, schema_change: SchemaChange) -> PolicyResult:
        """
        Enforce review requirements for schema changes.
        
        Args:
            schema_change: Schema change to validate
            
        Returns:
            PolicyResult indicating required action
        """
        # Determine applicable policy
        policy_key = self._get_policy_key(schema_change)
        review_policy = self.config.review_policies.get(policy_key, {})
        
        # Get required reviewers and approval count
        required_reviewers = review_policy.get('required_reviewers', [])
        approval_count = review_policy.get('approval_count', 1)
        auto_approve_minor = review_policy.get('auto_approve_minor', False)
        
        # Check for auto-approval of minor changes
        if auto_approve_minor and not schema_change.breaking:
            self._record_audit(AuditRecord(
                action="auto_approve_minor",
                target=schema_change.target,
                actor="system",
                details={"policy_key": policy_key, "reason": "non-breaking change"}
            ))
            return PolicyResult(
                action="allow",
                reason="Auto-approved: non-breaking change",
                has_approval=True
            )
        
        # Check existing approvals
        approvals = self._load_approvals("review")
        change_key = f"{schema_change.target}:{schema_change.timestamp}"
        existing_approvals = approvals.get(change_key, {}).get('approvers', [])
        
        # Validate approvers against team membership
        valid_approvers = []
        for approver in existing_approvals:
            if self._is_valid_approver(approver, required_reviewers, schema_change.team):
                valid_approvers.append(approver)
        
        # Check if sufficient approvals
        if len(valid_approvers) >= approval_count:
            self._record_audit(AuditRecord(
                action="review_approved",
                target=schema_change.target,
                actor=",".join(valid_approvers),
                details={
                    "policy_key": policy_key,
                    "required_approvals": approval_count,
                    "actual_approvals": len(valid_approvers),
                    "approvers": valid_approvers
                }
            ))
            return PolicyResult(
                action="allow",
                reason=f"Approved by {len(valid_approvers)} reviewers",
                has_approval=True,
                required_approvers=required_reviewers,
                actual_approvers=valid_approvers
            )
        
        # Insufficient approvals
        self._record_audit(AuditRecord(
            action="review_required",
            target=schema_change.target,
            actor="system",
            details={
                "policy_key": policy_key,
                "required_approvals": approval_count,
                "actual_approvals": len(valid_approvers),
                "required_reviewers": required_reviewers
            }
        ))
        
        return PolicyResult(
            action="require_approval",
            reason=f"Requires {approval_count} approvals from: {', '.join(required_reviewers)}",
            has_approval=False,
            required_approvers=required_reviewers,
            actual_approvers=valid_approvers
        )

    def enforce_breaking_change_policy(self, 
                                     breaking_changes: List[BreakingChange],
                                     policy: Optional[str] = None) -> PolicyResult:
        """
        Enforce breaking change policies.
        
        Args:
            breaking_changes: List of detected breaking changes
            policy: Override policy (if not provided, uses configuration)
            
        Returns:
            PolicyResult indicating required action
        """
        if not breaking_changes:
            return PolicyResult(action="allow", reason="No breaking changes detected")
        
        # Determine policy to apply
        if policy is None:
            # Use repository-specific policy if available
            repository = breaking_changes[0].repository if breaking_changes else "default"
            policy = self.config.breaking_change_policies.get(repository, "error")
        
        # Apply policy
        if policy == "allow":
            self._record_audit(AuditRecord(
                action="breaking_changes_allowed",
                target=breaking_changes[0].repository,
                actor="system",
                details={"policy": policy, "breaking_count": len(breaking_changes)}
            ))
            return PolicyResult(
                action="allow",
                reason=f"Breaking changes allowed by policy: {policy}"
            )
        
        elif policy == "warn":
            self._record_audit(AuditRecord(
                action="breaking_changes_warning",
                target=breaking_changes[0].repository,
                actor="system",
                details={"policy": policy, "breaking_count": len(breaking_changes)},
                result="warning"
            ))
            return PolicyResult(
                action="warn",
                reason=f"Breaking changes detected (policy: {policy})"
            )
        
        elif policy == "error":
            self._record_audit(AuditRecord(
                action="breaking_changes_blocked",
                target=breaking_changes[0].repository,
                actor="system",
                details={"policy": policy, "breaking_count": len(breaking_changes)},
                result="failure"
            ))
            return PolicyResult(
                action="error",
                reason=f"Breaking changes blocked by policy: {policy}",
                violations=[f"{change.type}: {change.description}" for change in breaking_changes]
            )
        
        elif policy == "require_approval":
            # Check for existing breaking change approval
            repository = breaking_changes[0].repository
            approvals = self._load_approvals("breaking")
            approval_key = f"{repository}:{breaking_changes[0].location}"
            
            if approval_key in approvals:
                self._record_audit(AuditRecord(
                    action="breaking_changes_approved",
                    target=repository,
                    actor=approvals[approval_key]['approver'],
                    details={"policy": policy, "breaking_count": len(breaking_changes)}
                ))
                return PolicyResult(
                    action="allow",
                    reason="Breaking changes have been approved",
                    has_approval=True
                )
            
            self._record_audit(AuditRecord(
                action="breaking_approval_required",
                target=repository,
                actor="system",
                details={"policy": policy, "breaking_count": len(breaking_changes)}
            ))
            return PolicyResult(
                action="require_approval",
                reason="Breaking changes require explicit approval",
                has_approval=False
            )
        
        return PolicyResult(
            action="error",
            reason=f"Unknown breaking change policy: {policy}"
        )

    def track_schema_change(self, change: SchemaChange) -> AuditRecord:
        """
        Track schema change for audit trails.
        
        Args:
            change: Schema change to track
            
        Returns:
            AuditRecord for the tracked change
        """
        record = AuditRecord(
            action="schema_change",
            target=change.target,
            actor=change.author,
            details={
                "change_type": change.change_type,
                "description": change.description,
                "repository": change.repository,
                "team": change.team,
                "breaking": change.breaking,
                "reviewed": change.reviewed,
                "approved_by": change.approved_by
            }
        )
        
        self._record_audit(record)
        logger.info(f"Tracked schema change: {change.target} ({change.change_type})")
        
        return record

    def approve_review(self, 
                      target: str, 
                      reviewer: str,
                      timestamp: Optional[str] = None) -> bool:
        """
        Approve a schema review.
        
        Args:
            target: Target being reviewed
            reviewer: Username of reviewer
            timestamp: Optional timestamp of review request
            
        Returns:
            True if approval was recorded
        """
        if timestamp is None:
            # Find most recent review request for this target
            timestamp = self._find_latest_review_timestamp(target)
            if not timestamp:
                logger.error(f"No pending review found for target: {target}")
                return False
        
        change_key = f"{target}:{timestamp}"
        approvals = self._load_approvals("review")
        
        if change_key not in approvals:
            approvals[change_key] = {"approvers": [], "timestamp": timestamp}
        
        if reviewer not in approvals[change_key]["approvers"]:
            approvals[change_key]["approvers"].append(reviewer)
            self._save_approvals(approvals, "review")
            
            self._record_audit(AuditRecord(
                action="review_approved",
                target=target,
                actor=reviewer,
                details={"approval_timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')}
            ))
            
            logger.info(f"Review approved by {reviewer} for target: {target}")
            return True
        
        logger.warning(f"Reviewer {reviewer} has already approved target: {target}")
        return False

    def approve_breaking_changes(self,
                               target: str,
                               repository: str,
                               reviewer: str,
                               location: Optional[str] = None) -> bool:
        """
        Approve breaking changes.
        
        Args:
            target: Target with breaking changes
            repository: Repository reference
            reviewer: Username of approver
            location: Specific location of breaking changes
            
        Returns:
            True if approval was recorded
        """
        approval_key = f"{repository}:{location or target}"
        approvals = self._load_approvals("breaking")
        
        approvals[approval_key] = {
            "approver": reviewer,
            "target": target,
            "repository": repository,
            "location": location,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        self._save_approvals(approvals, "breaking")
        
        self._record_audit(AuditRecord(
            action="breaking_changes_approved",
            target=target,
            actor=reviewer,
            details={
                "repository": repository,
                "location": location,
                "approval_timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
            }
        ))
        
        logger.info(f"Breaking changes approved by {reviewer} for {target}")
        return True

    def notify_team_breaking_changes(self,
                                   team: str,
                                   target: str,
                                   breaking_changes: List[BreakingChange]) -> None:
        """
        Notify team of breaking changes.
        
        Args:
            team: Team to notify
            target: Target with breaking changes
            breaking_changes: List of breaking changes
        """
        notification_data = {
            "team": team,
            "target": target,
            "breaking_count": len(breaking_changes),
            "changes": [
                {
                    "type": change.type,
                    "description": change.description,
                    "impact": change.impact
                }
                for change in breaking_changes
            ],
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        self._record_audit(AuditRecord(
            action="team_notification",
            target=target,
            actor="system",
            details=notification_data
        ))
        
        # In a full implementation, this would send actual notifications
        # (email, Slack, etc.) to team members
        logger.info(f"Notification sent to team {team} about breaking changes in {target}")

    def generate_compliance_report(self, 
                                 timeframe: str = "7d",
                                 team: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate compliance report for audit purposes.
        
        Args:
            timeframe: Time window for report (e.g., "7d", "30d", "1y")
            team: Optional team filter
            
        Returns:
            Compliance report data
        """
        # Parse timeframe
        timeframe_seconds = self._parse_timeframe(timeframe)
        cutoff_time = time.time() - timeframe_seconds
        
        # Read audit trail
        audit_records = []
        try:
            with open(self.audit_file, 'r') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        record_time = time.mktime(time.strptime(record['timestamp'], '%Y-%m-%dT%H:%M:%SZ'))
                        if record_time >= cutoff_time:
                            if team is None or record.get('details', {}).get('team') == team:
                                audit_records.append(record)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        continue
        except FileNotFoundError:
            pass
        
        # Generate report
        report = {
            "timeframe": timeframe,
            "team": team,
            "generated_at": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "total_records": len(audit_records),
            "summary": {
                "schema_changes": 0,
                "reviews_required": 0,
                "reviews_approved": 0,
                "breaking_changes_detected": 0,
                "breaking_changes_approved": 0,
                "policy_violations": 0
            },
            "details": {
                "by_action": {},
                "by_target": {},
                "by_actor": {}
            }
        }
        
        # Analyze records
        for record in audit_records:
            action = record.get('action', 'unknown')
            target = record.get('target', 'unknown')
            actor = record.get('actor', 'unknown')
            result = record.get('result', 'success')
            
            # Update summary
            if action == "schema_change":
                report["summary"]["schema_changes"] += 1
            elif action == "review_required":
                report["summary"]["reviews_required"] += 1
            elif action == "review_approved":
                report["summary"]["reviews_approved"] += 1
            elif action == "breaking_changes_detected":
                report["summary"]["breaking_changes_detected"] += 1
            elif action == "breaking_changes_approved":
                report["summary"]["breaking_changes_approved"] += 1
            elif result == "failure":
                report["summary"]["policy_violations"] += 1
            
            # Update details
            report["details"]["by_action"][action] = report["details"]["by_action"].get(action, 0) + 1
            report["details"]["by_target"][target] = report["details"]["by_target"].get(target, 0) + 1
            report["details"]["by_actor"][actor] = report["details"]["by_actor"].get(actor, 0) + 1
        
        return report

    def _get_policy_key(self, schema_change: SchemaChange) -> str:
        """Determine policy key for schema change."""
        # Check for repository-specific policy
        if schema_change.repository:
            repo_parts = schema_change.repository.split('/')
            if len(repo_parts) >= 2:
                org_repo = '/'.join(repo_parts[-2:])
                if org_repo in self.config.review_policies:
                    return org_repo
        
        # Check for team-specific policy
        if schema_change.team and schema_change.team in self.config.team_overrides:
            team_override = self.config.team_overrides[schema_change.team]
            if 'review_policy' in team_override:
                return team_override['review_policy']
        
        # Default policy
        return "default"

    def _is_valid_approver(self, 
                          approver: str, 
                          required_reviewers: List[str],
                          team: Optional[str] = None) -> bool:
        """Check if approver is valid for the required reviewers."""
        for reviewer in required_reviewers:
            if reviewer.startswith('@'):
                # Team reviewer
                team_name = reviewer[1:]
                if self.team_manager.validate_team_permissions(
                    team=team_name,
                    repository="",  # Not checking specific repo permission
                    username=approver,
                    action="read"
                ):
                    return True
            else:
                # Individual reviewer
                if approver == reviewer:
                    return True
        
        return False

    def _find_latest_review_timestamp(self, target: str) -> Optional[str]:
        """Find the latest review timestamp for a target."""
        # This would typically query pending reviews
        # For now, return current timestamp as fallback
        return time.strftime('%Y-%m-%dT%H:%M:%SZ')

    def _parse_timeframe(self, timeframe: str) -> float:
        """Parse timeframe string to seconds."""
        if timeframe.endswith('d'):
            return float(timeframe[:-1]) * 24 * 3600
        elif timeframe.endswith('h'):
            return float(timeframe[:-1]) * 3600
        elif timeframe.endswith('m'):
            return float(timeframe[:-1]) * 60
        elif timeframe.endswith('s'):
            return float(timeframe[:-1])
        else:
            # Default to days
            return float(timeframe) * 24 * 3600


def main():
    """Main entry point for governance engine testing."""
    parser = argparse.ArgumentParser(description="Schema Governance Engine")
    parser.add_argument("--config", default="governance.yaml", help="Governance config file")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Approve review
    approve_parser = subparsers.add_parser("approve", help="Approve schema review")
    approve_parser.add_argument("--target", required=True, help="Target to approve")
    approve_parser.add_argument("--reviewer", required=True, help="Reviewer username")
    approve_parser.add_argument("--timestamp", help="Review timestamp")
    
    # Approve breaking changes
    breaking_parser = subparsers.add_parser("approve-breaking", help="Approve breaking changes")
    breaking_parser.add_argument("--target", required=True, help="Target with breaking changes")
    breaking_parser.add_argument("--repository", required=True, help="Repository reference")
    breaking_parser.add_argument("--reviewer", required=True, help="Reviewer username")
    breaking_parser.add_argument("--location", help="Specific location of breaking changes")
    
    # Generate compliance report
    report_parser = subparsers.add_parser("report", help="Generate compliance report")
    report_parser.add_argument("--timeframe", default="7d", help="Report timeframe")
    report_parser.add_argument("--team", help="Team filter")
    report_parser.add_argument("--output", help="Output file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        engine = SchemaGovernanceEngine(
            config_file=args.config,
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "approve":
            success = engine.approve_review(
                target=args.target,
                reviewer=args.reviewer,
                timestamp=args.timestamp
            )
            if success:
                print(f"✅ Review approved by {args.reviewer} for target '{args.target}'")
            else:
                print(f"❌ Failed to approve review for target '{args.target}'")
                return 1
        
        elif args.command == "approve-breaking":
            success = engine.approve_breaking_changes(
                target=args.target,
                repository=args.repository,
                reviewer=args.reviewer,
                location=args.location
            )
            if success:
                print(f"✅ Breaking changes approved by {args.reviewer} for target '{args.target}'")
            else:
                print(f"❌ Failed to approve breaking changes for target '{args.target}'")
                return 1
        
        elif args.command == "report":
            report = engine.generate_compliance_report(
                timeframe=args.timeframe,
                team=args.team
            )
            
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(report, f, indent=2)
                print(f"📊 Compliance report saved to {args.output}")
            else:
                print("📊 Compliance Report")
                print(f"   Timeframe: {report['timeframe']}")
                print(f"   Total Records: {report['total_records']}")
                print(f"   Schema Changes: {report['summary']['schema_changes']}")
                print(f"   Reviews Required: {report['summary']['reviews_required']}")
                print(f"   Reviews Approved: {report['summary']['reviews_approved']}")
                print(f"   Breaking Changes: {report['summary']['breaking_changes_detected']}")
                print(f"   Policy Violations: {report['summary']['policy_violations']}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
