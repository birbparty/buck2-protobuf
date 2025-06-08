#!/usr/bin/env python3
"""
BSR Breaking Change Notification System.

This module provides Slack-focused team notifications for breaking changes
with intelligent escalation, interactive responses, and Buck2-specific guidance.
"""

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any
import logging

# Local imports
try:
    from .bsr_teams import BSRTeamManager, Team, TeamMember
    from .bsr_breaking_change_detector import BreakingChange, ChangeImpactAnalysis, MigrationPlan
except ImportError:
    # Handle direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent))
    from bsr_teams import BSRTeamManager, Team, TeamMember
    from bsr_breaking_change_detector import BreakingChange, ChangeImpactAnalysis, MigrationPlan

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NotificationMessage:
    """Represents a notification message for breaking changes."""
    message_id: str
    teams: List[str]
    breaking_changes: List[BreakingChange]
    severity: str  # low, medium, high, critical
    policy: str    # warn, error, review
    timestamp: str
    escalation_level: int = 0
    acknowledged_by: Set[str] = field(default_factory=set)
    responses: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Initialize notification with defaults."""
        if not self.message_id:
            self.message_id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ')

    @property
    def is_acknowledged(self) -> bool:
        """Check if notification is acknowledged by all teams."""
        return len(self.acknowledged_by) >= len(self.teams)

    @property
    def needs_escalation(self) -> bool:
        """Check if notification needs escalation."""
        return not self.is_acknowledged and self.severity in ["high", "critical"]

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            **asdict(self),
            'acknowledged_by': list(self.acknowledged_by),
            'breaking_changes': [change.to_dict() for change in self.breaking_changes],
        }


@dataclass 
class SlackMessage:
    """Represents a Slack message structure."""
    text: str
    blocks: List[Dict]
    thread_ts: Optional[str] = None
    channel: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to Slack API format."""
        payload = {
            "text": self.text,
            "blocks": self.blocks
        }
        if self.thread_ts:
            payload["thread_ts"] = self.thread_ts
        if self.channel:
            payload["channel"] = self.channel
        return payload


class SlackBreakingChangeNotifier:
    """
    Slack-focused breaking change notification system.
    
    Provides intelligent team notifications with escalation, interactive responses,
    and Buck2-specific migration guidance delivery.
    """
    
    def __init__(self,
                 team_manager: Optional[BSRTeamManager] = None,
                 default_webhook: Optional[str] = None,
                 cache_dir: Union[str, Path] = None,
                 verbose: bool = False):
        """
        Initialize the Slack notification system.
        
        Args:
            team_manager: Team manager for team coordination
            default_webhook: Default Slack webhook URL
            cache_dir: Directory for notification state cache
            verbose: Enable verbose logging
        """
        self.team_manager = team_manager or BSRTeamManager(verbose=verbose)
        self.default_webhook = default_webhook or os.getenv('SLACK_WEBHOOK_URL')
        self.verbose = verbose
        
        # Set up cache directory
        if cache_dir is None:
            cache_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'notifications'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Notification tracking
        self.notification_state_file = self.cache_dir / 'notification_state.json'
        self.active_notifications: Dict[str, NotificationMessage] = {}
        
        # Load existing notification state
        self._load_notification_state()
        
        if self.verbose:
            logger.info("Slack Breaking Change Notifier initialized")

    def send_breaking_change_notification(self,
                                        teams: List[str],
                                        breaking_changes: List[BreakingChange],
                                        impact_analysis: ChangeImpactAnalysis,
                                        migration_plan: MigrationPlan,
                                        policy: str = "warn",
                                        slack_webhook: Optional[str] = None) -> str:
        """
        Send comprehensive breaking change notification to teams.
        
        Args:
            teams: List of team names to notify
            breaking_changes: List of breaking changes detected
            impact_analysis: Impact analysis results
            migration_plan: Generated migration plan
            policy: Breaking change policy (warn, error, review)
            slack_webhook: Slack webhook URL (overrides default)
            
        Returns:
            Notification message ID
        """
        # Determine severity based on impact analysis
        severity = self._determine_severity(breaking_changes, impact_analysis)
        
        # Create notification message
        notification = NotificationMessage(
            message_id=str(uuid.uuid4()),
            teams=teams,
            breaking_changes=breaking_changes,
            severity=severity,
            policy=policy,
            timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ')
        )
        
        # Store notification for tracking
        self.active_notifications[notification.message_id] = notification
        self._save_notification_state()
        
        # Create Slack message
        slack_message = self._create_comprehensive_slack_message(
            notification, impact_analysis, migration_plan
        )
        
        # Send to each team
        webhook_url = slack_webhook or self.default_webhook
        if webhook_url:
            success = self._send_slack_message(slack_message, webhook_url)
            if success:
                logger.info(f"Sent breaking change notification {notification.message_id} to {len(teams)} teams")
            else:
                logger.error(f"Failed to send notification {notification.message_id}")
        else:
            logger.warning("No Slack webhook configured, notification not sent")
        
        return notification.message_id

    def send_migration_guidance(self,
                               teams: List[str],
                               migration_plan: MigrationPlan,
                               parent_message_id: Optional[str] = None,
                               slack_webhook: Optional[str] = None) -> bool:
        """
        Send detailed migration guidance to teams.
        
        Args:
            teams: List of team names 
            migration_plan: Migration plan to deliver
            parent_message_id: Parent notification to thread under
            slack_webhook: Slack webhook URL
            
        Returns:
            True if sent successfully
        """
        # Create migration guidance message
        slack_message = self._create_migration_guidance_message(migration_plan)
        
        # Send message
        webhook_url = slack_webhook or self.default_webhook
        if webhook_url:
            return self._send_slack_message(slack_message, webhook_url)
        
        return False

    def handle_acknowledgment(self,
                            message_id: str,
                            team_or_user: str,
                            response: str = "acknowledged") -> bool:
        """
        Handle acknowledgment from team or user.
        
        Args:
            message_id: Notification message ID
            team_or_user: Team name or username acknowledging
            response: Acknowledgment response
            
        Returns:
            True if acknowledgment processed
        """
        if message_id not in self.active_notifications:
            return False
        
        notification = self.active_notifications[message_id]
        notification.acknowledged_by.add(team_or_user)
        notification.responses[team_or_user] = response
        
        # Check if fully acknowledged
        if notification.is_acknowledged:
            logger.info(f"Notification {message_id} fully acknowledged")
            # Could send confirmation message here
        
        self._save_notification_state()
        return True

    def check_escalation_needed(self, escalation_hours: List[int] = [2, 24]) -> List[str]:
        """
        Check for notifications that need escalation.
        
        Args:
            escalation_hours: Hours after which to escalate
            
        Returns:
            List of message IDs that need escalation
        """
        needs_escalation = []
        current_time = time.time()
        
        for message_id, notification in self.active_notifications.items():
            if notification.is_acknowledged:
                continue
            
            # Calculate time since notification
            notification_time = time.mktime(time.strptime(
                notification.timestamp, '%Y-%m-%dT%H:%M:%SZ'
            ))
            hours_elapsed = (current_time - notification_time) / 3600
            
            # Check escalation thresholds
            for threshold in escalation_hours:
                if (hours_elapsed >= threshold and 
                    notification.escalation_level < len(escalation_hours) and
                    notification.needs_escalation):
                    needs_escalation.append(message_id)
                    notification.escalation_level += 1
                    break
        
        self._save_notification_state()
        return needs_escalation

    def send_escalation_notice(self,
                             message_id: str,
                             escalation_teams: List[str],
                             slack_webhook: Optional[str] = None) -> bool:
        """
        Send escalation notice for unacknowledged breaking changes.
        
        Args:
            message_id: Original notification message ID
            escalation_teams: Teams to escalate to (usually parent teams)
            slack_webhook: Slack webhook URL
            
        Returns:
            True if escalation sent successfully
        """
        if message_id not in self.active_notifications:
            return False
        
        notification = self.active_notifications[message_id]
        
        # Create escalation message
        slack_message = self._create_escalation_message(notification, escalation_teams)
        
        # Send escalation
        webhook_url = slack_webhook or self.default_webhook
        if webhook_url:
            success = self._send_slack_message(slack_message, webhook_url)
            if success:
                logger.info(f"Sent escalation for notification {message_id} to {escalation_teams}")
            return success
        
        return False

    def get_notification_status(self, message_id: str) -> Optional[Dict]:
        """Get status of a notification."""
        if message_id not in self.active_notifications:
            return None
        
        notification = self.active_notifications[message_id]
        return {
            "message_id": message_id,
            "acknowledged": notification.is_acknowledged,
            "acknowledged_by": list(notification.acknowledged_by),
            "needs_escalation": notification.needs_escalation,
            "escalation_level": notification.escalation_level,
            "teams": notification.teams,
            "severity": notification.severity,
            "timestamp": notification.timestamp,
        }

    def _determine_severity(self,
                           breaking_changes: List[BreakingChange],
                           impact_analysis: ChangeImpactAnalysis) -> str:
        """Determine notification severity based on changes and impact."""
        critical_count = len([c for c in breaking_changes if c.severity == "critical"])
        total_score = sum(change.impact_score for change in breaking_changes)
        
        if critical_count > 0 or total_score > 30:
            return "critical"
        elif total_score > 15 or impact_analysis.coordination_required:
            return "high"
        elif total_score > 5:
            return "medium"
        else:
            return "low"

    def _create_comprehensive_slack_message(self,
                                          notification: NotificationMessage,
                                          impact_analysis: ChangeImpactAnalysis,
                                          migration_plan: MigrationPlan) -> SlackMessage:
        """Create comprehensive Slack message for breaking changes."""
        severity_emojis = {
            "low": "🟢",
            "medium": "🟡", 
            "high": "🟠",
            "critical": "🔴"
        }
        
        policy_emojis = {
            "warn": "⚠️",
            "error": "❌",
            "review": "👀"
        }
        
        severity_emoji = severity_emojis.get(notification.severity, "⚠️")
        policy_emoji = policy_emojis.get(notification.policy, "⚠️")
        
        # Main header block
        header_text = (f"*Breaking Changes Detected* {severity_emoji} {policy_emoji}\n\n"
                      f"*Baseline:* `{impact_analysis.affected_repositories[0] if impact_analysis.affected_repositories else 'Unknown'}`\n"
                      f"*Policy:* {notification.policy.upper()}\n"
                      f"*Issues:* {len(notification.breaking_changes)}\n"
                      f"*Critical:* {len([c for c in notification.breaking_changes if c.severity == 'critical'])}")
        
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header_text
                }
            },
            {"type": "divider"}
        ]
        
        # Breaking changes summary
        if notification.breaking_changes:
            changes_text = "*Top Breaking Changes:*\n"
            for i, change in enumerate(notification.breaking_changes[:3], 1):
                severity_icon = "🔴" if change.severity == "critical" else "🟡" if change.severity == "major" else "🟢"
                changes_text += f"{severity_icon} `{change.path}`: {change.message[:80]}...\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": changes_text
                }
            })
        
        # Buck2 impact summary
        if impact_analysis.buck2_targets_affected:
            buck2_text = f"*Buck2 Impact:*\n• {len(impact_analysis.buck2_targets_affected)} targets affected\n• Build verification required"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": buck2_text
                }
            })
        
        # Migration plan summary
        migration_text = (f"*Migration Plan:*\n"
                         f"• Risk Level: {migration_plan.risk_level}\n"
                         f"• Estimated Duration: {migration_plan.estimated_duration}\n"
                         f"• Migration Steps: {len(migration_plan.migration_steps)}")
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": migration_text
            }
        })
        
        blocks.append({"type": "divider"})
        
        # Action buttons
        actions = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📋 View Migration Plan"},
                    "style": "primary",
                    "value": f"view_migration_{notification.message_id}"
                },
                {
                    "type": "button", 
                    "text": {"type": "plain_text", "text": "✅ Acknowledge"},
                    "style": "primary",
                    "value": f"acknowledge_{notification.message_id}"
                }
            ]
        }
        
        # Add escalation button for high/critical severity
        if notification.severity in ["high", "critical"]:
            actions["elements"].append({
                "type": "button",
                "text": {"type": "plain_text", "text": "🚨 Need Help"},
                "style": "danger",
                "value": f"escalate_{notification.message_id}"
            })
        
        blocks.append(actions)
        
        # Team coordination info
        if len(notification.teams) > 1:
            team_text = f"*Teams to Coordinate:* {', '.join(notification.teams)}"
            blocks.append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": team_text}]
            })
        
        main_text = f"{severity_emoji} Breaking changes detected ({len(notification.breaking_changes)} issues)"
        
        return SlackMessage(text=main_text, blocks=blocks)

    def _create_migration_guidance_message(self, migration_plan: MigrationPlan) -> SlackMessage:
        """Create detailed migration guidance message."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📋 Migration Plan: {migration_plan.summary}*"
                }
            },
            {"type": "divider"}
        ]
        
        # Migration steps
        if migration_plan.migration_steps:
            steps_text = "*Migration Steps:*\n"
            for i, step in enumerate(migration_plan.migration_steps, 1):
                steps_text += f"{i}. *{step['title']}*\n   {step['description'][:100]}...\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": steps_text
                }
            })
        
        # Buck2 commands
        if migration_plan.buck2_commands:
            commands_text = "*Key Buck2 Commands:*\n```\n" + "\n".join(migration_plan.buck2_commands[:5]) + "\n```"
            blocks.append({
                "type": "section", 
                "text": {
                    "type": "mrkdwn",
                    "text": commands_text
                }
            })
        
        # Testing strategy
        if migration_plan.testing_strategy:
            testing_text = "*Testing Strategy:*\n" + "\n".join([f"• {test}" for test in migration_plan.testing_strategy[:3]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": testing_text
                }
            })
        
        # Rollback plan
        rollback_text = "*Rollback Plan:*\n" + "\n".join([f"{i}. {step}" for i, step in enumerate(migration_plan.rollback_plan[:3], 1)])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": rollback_text
            }
        })
        
        return SlackMessage(
            text="📋 Migration Plan Available",
            blocks=blocks
        )

    def _create_escalation_message(self,
                                 notification: NotificationMessage,
                                 escalation_teams: List[str]) -> SlackMessage:
        """Create escalation message for unacknowledged notifications."""
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚨 *ESCALATION: Unacknowledged Breaking Changes*\n\n"
                           f"Notification ID: `{notification.message_id}`\n"
                           f"Original Teams: {', '.join(notification.teams)}\n"
                           f"Severity: {notification.severity.upper()}\n"
                           f"Breaking Changes: {len(notification.breaking_changes)}"
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Action Required:*\n"
                           "• Review breaking changes with original teams\n"
                           "• Ensure migration planning is proceeding\n"
                           "• Coordinate timeline if blocking"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "👀 Take Ownership"},
                        "style": "primary",
                        "value": f"take_ownership_{notification.message_id}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📞 Contact Teams"},
                        "value": f"contact_teams_{notification.message_id}"
                    }
                ]
            }
        ]
        
        return SlackMessage(
            text=f"🚨 Escalation: Unacknowledged breaking changes (ID: {notification.message_id})",
            blocks=blocks
        )

    def _send_slack_message(self, message: SlackMessage, webhook_url: str) -> bool:
        """Send message to Slack via webhook."""
        try:
            import requests
            
            payload = message.to_dict()
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                if self.verbose:
                    logger.info("Slack message sent successfully")
                return True
            else:
                logger.error(f"Slack webhook returned status {response.status_code}: {response.text}")
                return False
                
        except ImportError:
            logger.error("requests library not available, cannot send Slack notifications")
            return False
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    def _load_notification_state(self) -> None:
        """Load notification state from cache."""
        if not self.notification_state_file.exists():
            return
        
        try:
            with open(self.notification_state_file, 'r') as f:
                state_data = json.load(f)
            
            for message_id, notification_data in state_data.items():
                # Reconstruct breaking changes
                breaking_changes = []
                for change_data in notification_data.get('breaking_changes', []):
                    breaking_changes.append(BreakingChange(**change_data))
                
                # Reconstruct notification
                notification_data['breaking_changes'] = breaking_changes
                notification_data['acknowledged_by'] = set(notification_data.get('acknowledged_by', []))
                
                self.active_notifications[message_id] = NotificationMessage(**notification_data)
                
            logger.info(f"Loaded {len(self.active_notifications)} active notifications")
            
        except Exception as e:
            logger.error(f"Failed to load notification state: {e}")

    def _save_notification_state(self) -> None:
        """Save notification state to cache."""
        try:
            state_data = {}
            for message_id, notification in self.active_notifications.items():
                state_data[message_id] = notification.to_dict()
            
            with open(self.notification_state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save notification state: {e}")


def main():
    """Main entry point for notification system testing."""
    parser = argparse.ArgumentParser(description="BSR Breaking Change Notification System")
    parser.add_argument("--webhook", help="Slack webhook URL")
    parser.add_argument("--teams", nargs="+", help="Teams to notify")
    parser.add_argument("--test-message", action="store_true", help="Send test message")
    parser.add_argument("--check-escalations", action="store_true", help="Check for escalations")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        notifier = SlackBreakingChangeNotifier(
            default_webhook=args.webhook,
            verbose=args.verbose
        )
        
        if args.test_message:
            # Create test notification
            test_changes = [
                BreakingChange(
                    type="FIELD_NO_DELETE",
                    path="api/user.proto",
                    message="Field 'email' was deleted",
                    severity="major",
                    rule="FIELD_NO_DELETE",
                    category="wire"
                )
            ]
            
            # Mock impact analysis
            from bsr_breaking_change_detector import ChangeImpactAnalysis, MigrationPlan
            
            impact_analysis = ChangeImpactAnalysis(
                breaking_changes=test_changes,
                affected_teams=args.teams or ["test-team"],
                affected_repositories=["buf.build/test/api"],
                buck2_targets_affected=["//api:user_proto"],
                migration_complexity="medium",
                estimated_migration_time="30-60 minutes",
                consumer_impact={"test-team": ["Update user service"]},
                rollback_complexity="low",
                coordination_required=False
            )
            
            migration_plan = MigrationPlan(
                summary="Test migration plan",
                breaking_changes=test_changes,
                migration_steps=[{
                    "title": "Update proto definitions",
                    "description": "Remove references to deleted field"
                }],
                buck2_commands=["buck2 build //api:user_proto"],
                file_updates={},
                testing_strategy=["Run integration tests"],
                rollback_plan=["Restore previous proto"],
                team_coordination={},
                estimated_duration="30 minutes",
                risk_level="medium"
            )
            
            message_id = notifier.send_breaking_change_notification(
                teams=args.teams or ["test-team"],
                breaking_changes=test_changes,
                impact_analysis=impact_analysis,
                migration_plan=migration_plan
            )
            
            print(f"Sent test notification: {message_id}")
        
        elif args.check_escalations:
            escalations = notifier.check_escalation_needed()
            if escalations:
                print(f"Found {len(escalations)} notifications needing escalation:")
                for message_id in escalations:
                    status = notifier.get_notification_status(message_id)
                    print(f"  {message_id}: {status}")
            else:
                print("No escalations needed")
        
        else:
            parser.print_help()
    
    except Exception as e:
        print(f"ERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
