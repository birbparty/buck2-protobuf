#!/usr/bin/env python3
"""
Multi-Platform Notification Manager for Team Collaboration.

This module provides multi-platform notification capabilities for schema changes,
supporting Slack, Microsoft Teams, Email, and Webhooks for comprehensive
team communication and coordination.
"""

import argparse
import json
import os
import time
import uuid
import smtplib
import ssl
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlencode
import logging

# Try to import requests for HTTP operations
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("Warning: requests library not available. HTTP notifications will be disabled.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class NotificationTemplate:
    """Template for formatting notifications."""
    template_type: str  # "change_detected", "review_required", "breaking_change", etc.
    title_template: str
    body_template: str
    priority: str = "normal"  # "low", "normal", "high", "critical"
    format_type: str = "text"  # "text", "markdown", "html"
    include_fields: List[str] = field(default_factory=list)


@dataclass
class NotificationResult:
    """Result of a notification send operation."""
    channel_type: str
    success: bool
    message_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationError(Exception):
    """Notification operation failed."""
    pass


class BaseNotifier:
    """Base class for platform-specific notifiers."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        """
        Initialize base notifier.
        
        Args:
            config: Configuration for this notifier
            verbose: Enable verbose logging
        """
        self.config = config
        self.verbose = verbose
        self.enabled = config.get('enabled', True)
        
    def send_notification(self, 
                         message: Dict[str, Any],
                         template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """
        Send notification using this notifier.
        
        Args:
            message: Message data to send
            template: Optional template for formatting
            
        Returns:
            NotificationResult with send status
        """
        if not self.enabled:
            return NotificationResult(
                channel_type=self.__class__.__name__,
                success=False,
                error_message="Notifier disabled"
            )
        
        try:
            return self._send_notification_impl(message, template)
        except Exception as e:
            logger.error(f"Notification failed for {self.__class__.__name__}: {e}")
            return NotificationResult(
                channel_type=self.__class__.__name__,
                success=False,
                error_message=str(e)
            )
    
    def _send_notification_impl(self, 
                               message: Dict[str, Any],
                               template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """Implementation-specific notification sending."""
        raise NotImplementedError("Subclasses must implement _send_notification_impl")
    
    def _format_message(self, 
                       message: Dict[str, Any],
                       template: Optional[NotificationTemplate] = None) -> Dict[str, str]:
        """Format message using template."""
        if not template:
            return {
                "title": message.get('schema_target', 'Schema Change'),
                "body": json.dumps(message, indent=2)
            }
        
        # Apply template formatting
        title = template.title_template.format(**message)
        body = template.body_template.format(**message)
        
        return {
            "title": title,
            "body": body,
            "format": template.format_type,
            "priority": template.priority
        }


class SlackNotifier(BaseNotifier):
    """Slack notification implementation."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        super().__init__(config, verbose)
        self.webhook_url = config.get('webhook_url')
        self.channel = config.get('channel', '#general')
        self.username = config.get('username', 'Schema Bot')
        self.icon_emoji = config.get('icon_emoji', ':robot_face:')
        
        if not self.webhook_url and self.enabled:
            logger.warning("Slack webhook URL not configured, disabling Slack notifications")
            self.enabled = False
    
    def _send_notification_impl(self, 
                               message: Dict[str, Any],
                               template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """Send notification to Slack."""
        if not HAS_REQUESTS:
            raise NotificationError("requests library required for Slack notifications")
        
        formatted = self._format_message(message, template)
        
        # Create Slack payload
        slack_payload = {
            "channel": self.channel,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "text": formatted["title"],
            "attachments": [
                {
                    "color": self._get_color_for_priority(formatted.get("priority", "normal")),
                    "fields": [
                        {
                            "title": "Details",
                            "value": formatted["body"],
                            "short": False
                        }
                    ],
                    "footer": "Buck2 Protobuf Schema Tracker",
                    "ts": int(time.time())
                }
            ]
        }
        
        # Add custom fields based on message content
        fields = []
        if message.get('change_type'):
            fields.append({
                "title": "Change Type",
                "value": message['change_type'].title(),
                "short": True
            })
        
        if message.get('impact_level'):
            fields.append({
                "title": "Impact Level",
                "value": message['impact_level'].title(),
                "short": True
            })
        
        if message.get('repository'):
            fields.append({
                "title": "Repository",
                "value": message['repository'],
                "short": True
            })
        
        if message.get('created_by'):
            fields.append({
                "title": "Author",
                "value": message['created_by'],
                "short": True
            })
        
        if fields:
            slack_payload["attachments"][0]["fields"] = fields
        
        # Send to Slack
        response = requests.post(
            self.webhook_url,
            json=slack_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return NotificationResult(
                channel_type="slack",
                success=True,
                message_id=f"slack_{int(time.time())}",
                metadata={"channel": self.channel}
            )
        else:
            raise NotificationError(f"Slack API error: {response.status_code} - {response.text}")
    
    def _get_color_for_priority(self, priority: str) -> str:
        """Get Slack color for priority level."""
        colors = {
            "low": "good",
            "normal": "#439FE0",
            "high": "warning",
            "critical": "danger"
        }
        return colors.get(priority, "#439FE0")


class TeamsNotifier(BaseNotifier):
    """Microsoft Teams notification implementation."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        super().__init__(config, verbose)
        self.webhook_url = config.get('webhook_url')
        
        if not self.webhook_url and self.enabled:
            logger.warning("Teams webhook URL not configured, disabling Teams notifications")
            self.enabled = False
    
    def _send_notification_impl(self, 
                               message: Dict[str, Any],
                               template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """Send notification to Microsoft Teams."""
        if not HAS_REQUESTS:
            raise NotificationError("requests library required for Teams notifications")
        
        formatted = self._format_message(message, template)
        
        # Create Teams adaptive card payload
        teams_payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": self._get_color_for_priority(formatted.get("priority", "normal")),
            "summary": formatted["title"],
            "sections": [
                {
                    "activityTitle": formatted["title"],
                    "activitySubtitle": f"Schema change in {message.get('repository', 'unknown repository')}",
                    "facts": []
                }
            ]
        }
        
        # Add facts based on message content
        facts = []
        if message.get('change_type'):
            facts.append({
                "name": "Change Type",
                "value": message['change_type'].title()
            })
        
        if message.get('impact_level'):
            facts.append({
                "name": "Impact Level", 
                "value": message['impact_level'].title()
            })
        
        if message.get('created_by'):
            facts.append({
                "name": "Author",
                "value": message['created_by']
            })
        
        if message.get('breaking_changes_count', 0) > 0:
            facts.append({
                "name": "Breaking Changes",
                "value": str(message['breaking_changes_count'])
            })
        
        if message.get('review_required'):
            facts.append({
                "name": "Review Required",
                "value": "Yes" if message['review_required'] else "No"
            })
        
        teams_payload["sections"][0]["facts"] = facts
        
        # Add text section with details
        if formatted["body"] != formatted["title"]:
            teams_payload["sections"].append({
                "text": formatted["body"]
            })
        
        # Send to Teams
        response = requests.post(
            self.webhook_url,
            json=teams_payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return NotificationResult(
                channel_type="teams",
                success=True,
                message_id=f"teams_{int(time.time())}"
            )
        else:
            raise NotificationError(f"Teams API error: {response.status_code} - {response.text}")
    
    def _get_color_for_priority(self, priority: str) -> str:
        """Get Teams color for priority level."""
        colors = {
            "low": "00FF00",
            "normal": "0078D4", 
            "high": "FF8C00",
            "critical": "FF0000"
        }
        return colors.get(priority, "0078D4")


class EmailNotifier(BaseNotifier):
    """Email notification implementation."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        super().__init__(config, verbose)
        self.smtp_server = config.get('smtp_server')
        self.smtp_port = config.get('smtp_port', 587)
        self.username = config.get('username')
        self.password = config.get('password')
        self.from_address = config.get('from_address')
        self.use_tls = config.get('use_tls', True)
        
        if not all([self.smtp_server, self.username, self.password, self.from_address]) and self.enabled:
            logger.warning("Email configuration incomplete, disabling email notifications")
            self.enabled = False
    
    def _send_notification_impl(self, 
                               message: Dict[str, Any],
                               template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """Send email notification."""
        formatted = self._format_message(message, template)
        
        # Get recipients from message or config
        recipients = message.get('email_recipients', self.config.get('default_recipients', []))
        if not recipients:
            raise NotificationError("No email recipients specified")
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = self.from_address
        msg['To'] = ", ".join(recipients)
        msg['Subject'] = formatted["title"]
        
        # Create email body
        body = self._create_email_body(message, formatted)
        msg.attach(MIMEText(body, 'html' if formatted.get("format") == "html" else 'plain'))
        
        # Send email
        context = ssl.create_default_context()
        
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            if self.use_tls:
                server.starttls(context=context)
            server.login(self.username, self.password)
            server.send_message(msg)
        
        return NotificationResult(
            channel_type="email",
            success=True,
            message_id=f"email_{int(time.time())}",
            metadata={"recipients": recipients}
        )
    
    def _create_email_body(self, message: Dict[str, Any], formatted: Dict[str, str]) -> str:
        """Create detailed email body."""
        body_parts = [formatted["body"]]
        
        # Add detailed information
        body_parts.append("\n\n--- Change Details ---")
        
        if message.get('schema_target'):
            body_parts.append(f"Schema Target: {message['schema_target']}")
        
        if message.get('repository'):
            body_parts.append(f"Repository: {message['repository']}")
        
        if message.get('created_by'):
            body_parts.append(f"Author: {message['created_by']}")
        
        if message.get('commit_hash'):
            body_parts.append(f"Commit: {message['commit_hash']}")
        
        if message.get('branch'):
            body_parts.append(f"Branch: {message['branch']}")
        
        if message.get('breaking_changes_count', 0) > 0:
            body_parts.append(f"Breaking Changes: {message['breaking_changes_count']}")
        
        if message.get('review_id'):
            body_parts.append(f"Review ID: {message['review_id']}")
        
        if message.get('recommendations'):
            body_parts.append("\n--- Recommendations ---")
            for i, rec in enumerate(message['recommendations'], 1):
                body_parts.append(f"{i}. {rec}")
        
        return "\n".join(body_parts)


class WebhookNotifier(BaseNotifier):
    """Generic webhook notification implementation."""
    
    def __init__(self, config: Dict[str, Any], verbose: bool = False):
        super().__init__(config, verbose)
        self.webhook_url = config.get('webhook_url')
        self.method = config.get('method', 'POST').upper()
        self.headers = config.get('headers', {})
        self.auth = config.get('auth')
        
        if not self.webhook_url and self.enabled:
            logger.warning("Webhook URL not configured, disabling webhook notifications")
            self.enabled = False
    
    def _send_notification_impl(self, 
                               message: Dict[str, Any],
                               template: Optional[NotificationTemplate] = None) -> NotificationResult:
        """Send webhook notification."""
        if not HAS_REQUESTS:
            raise NotificationError("requests library required for webhook notifications")
        
        formatted = self._format_message(message, template)
        
        # Create webhook payload
        payload = {
            "notification": {
                "title": formatted["title"],
                "body": formatted["body"],
                "priority": formatted.get("priority", "normal"),
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
            },
            "message": message
        }
        
        # Prepare request
        request_kwargs = {
            "url": self.webhook_url,
            "timeout": 30,
            "headers": self.headers
        }
        
        if self.auth:
            if self.auth.get('type') == 'bearer':
                request_kwargs['headers']['Authorization'] = f"Bearer {self.auth['token']}"
            elif self.auth.get('type') == 'basic':
                request_kwargs['auth'] = (self.auth['username'], self.auth['password'])
        
        # Send request
        if self.method == 'POST':
            request_kwargs['json'] = payload
            response = requests.post(**request_kwargs)
        elif self.method == 'PUT':
            request_kwargs['json'] = payload
            response = requests.put(**request_kwargs)
        elif self.method == 'GET':
            request_kwargs['params'] = {'payload': json.dumps(payload)}
            response = requests.get(**request_kwargs)
        else:
            raise NotificationError(f"Unsupported HTTP method: {self.method}")
        
        if response.status_code in [200, 201, 202]:
            return NotificationResult(
                channel_type="webhook",
                success=True,
                message_id=f"webhook_{int(time.time())}",
                metadata={"status_code": response.status_code}
            )
        else:
            raise NotificationError(f"Webhook error: {response.status_code} - {response.text}")


class NotificationManager:
    """
    Multi-platform notification management system.
    
    Coordinates notifications across Slack, Teams, Email, and Webhooks
    with template support and delivery tracking.
    """
    
    def __init__(self,
                 config: Dict[str, Any] = None,
                 storage_dir: Union[str, Path] = None,
                 verbose: bool = False):
        """
        Initialize Notification Manager.
        
        Args:
            config: Notification configuration
            storage_dir: Storage directory for templates and logs
            verbose: Enable verbose logging
        """
        if storage_dir is None:
            storage_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'notifications'
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        self.config = config or {}
        
        # Storage files
        self.templates_file = self.storage_dir / "templates.json"
        self.delivery_log_file = self.storage_dir / "delivery_log.json"
        
        # Initialize notifiers
        self.notifiers = {}
        self._init_notifiers()
        
        # Load templates
        self.templates = self._load_templates()
        
        logger.info(f"Notification Manager initialized with {len(self.notifiers)} channels")
    
    def _init_notifiers(self) -> None:
        """Initialize platform-specific notifiers."""
        notifier_classes = {
            'slack': SlackNotifier,
            'teams': TeamsNotifier,
            'email': EmailNotifier,
            'webhook': WebhookNotifier
        }
        
        for platform, notifier_class in notifier_classes.items():
            platform_config = self.config.get(platform, {})
            if platform_config:
                try:
                    self.notifiers[platform] = notifier_class(platform_config, self.verbose)
                    logger.info(f"Initialized {platform} notifier")
                except Exception as e:
                    logger.error(f"Failed to initialize {platform} notifier: {e}")
    
    def _load_templates(self) -> Dict[str, NotificationTemplate]:
        """Load notification templates."""
        try:
            with open(self.templates_file, 'r') as f:
                templates_data = json.load(f)
            
            templates = {}
            for template_name, template_data in templates_data.items():
                templates[template_name] = NotificationTemplate(**template_data)
            
            return templates
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default templates
            return self._get_default_templates()
    
    def _get_default_templates(self) -> Dict[str, NotificationTemplate]:
        """Get default notification templates."""
        return {
            "change_detected": NotificationTemplate(
                template_type="change_detected",
                title_template="🔄 Schema Change: {schema_target}",
                body_template="A {change_type} change was detected in {schema_target}.\nRepository: {repository}\nImpact: {impact_level}",
                priority="normal",
                format_type="text"
            ),
            "breaking_change": NotificationTemplate(
                template_type="breaking_change",
                title_template="🚨 Breaking Change Alert: {schema_target}",
                body_template="Breaking changes detected in {schema_target}!\n{breaking_changes_count} breaking changes found.\nImmediate attention required.",
                priority="critical",
                format_type="text"
            ),
            "review_required": NotificationTemplate(
                template_type="review_required",
                title_template="📋 Review Required: {schema_target}",
                body_template="Schema changes in {schema_target} require review.\nReview ID: {review_id}\nPlease review and approve changes.",
                priority="high",
                format_type="text"
            ),
            "migration_required": NotificationTemplate(
                template_type="migration_required",
                title_template="🔧 Migration Required: {schema_target}",
                body_template="Changes to {schema_target} require migration.\nEstimated time: {estimated_migration_time}\nMigration complexity: {migration_complexity}",
                priority="high",
                format_type="text"
            )
        }
    
    def send_notification(self,
                         message: Dict[str, Any],
                         channels: List[str] = None,
                         template_name: Optional[str] = None) -> Dict[str, NotificationResult]:
        """
        Send notification across specified channels.
        
        Args:
            message: Message data to send
            channels: List of channels to send to (default: all enabled)
            template_name: Name of template to use
            
        Returns:
            Dictionary mapping channel names to NotificationResult
        """
        if channels is None:
            channels = list(self.notifiers.keys())
        
        # Get template
        template = None
        if template_name and template_name in self.templates:
            template = self.templates[template_name]
        elif message.get('type') in self.templates:
            template = self.templates[message['type']]
        
        # Send to each channel
        results = {}
        for channel in channels:
            if channel in self.notifiers:
                notifier = self.notifiers[channel]
                result = notifier.send_notification(message, template)
                results[channel] = result
                
                # Log delivery
                self._log_delivery(channel, message, result)
            else:
                logger.warning(f"Unknown notification channel: {channel}")
                results[channel] = NotificationResult(
                    channel_type=channel,
                    success=False,
                    error_message="Unknown channel"
                )
        
        return results
    
    def send_change_notification(self,
                               change_record: Dict[str, Any],
                               channels: List[str] = None) -> Dict[str, NotificationResult]:
        """
        Send schema change notification with appropriate template.
        
        Args:
            change_record: Change record data
            channels: Channels to send to
            
        Returns:
            Notification results
        """
        # Determine appropriate template based on change characteristics
        template_name = "change_detected"
        
        if change_record.get('breaking_changes_count', 0) > 0:
            template_name = "breaking_change"
        elif change_record.get('review_required'):
            template_name = "review_required"
        elif change_record.get('migration_required'):
            template_name = "migration_required"
        
        return self.send_notification(change_record, channels, template_name)
    
    def add_template(self, name: str, template: NotificationTemplate) -> None:
        """Add or update a notification template."""
        self.templates[name] = template
        self._save_templates()
        logger.info(f"Added template: {name}")
    
    def get_delivery_stats(self, 
                          timeframe: str = "24h",
                          channel: Optional[str] = None) -> Dict[str, Any]:
        """
        Get notification delivery statistics.
        
        Args:
            timeframe: Time period to analyze
            channel: Specific channel to analyze
            
        Returns:
            Delivery statistics
        """
        # Calculate time boundary
        hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(timeframe, 24)
        since_timestamp = time.strftime(
            '%Y-%m-%dT%H:%M:%SZ',
            time.gmtime(time.time() - hours * 3600)
        )
        
        # Load delivery log
        try:
            with open(self.delivery_log_file, 'r') as f:
                delivery_log = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            delivery_log = {"deliveries": []}
        
        # Filter deliveries
        deliveries = []
        for delivery in delivery_log.get("deliveries", []):
            if delivery.get("timestamp", "") >= since_timestamp:
                if channel is None or delivery.get("channel") == channel:
                    deliveries.append(delivery)
        
        # Calculate statistics
        total_attempts = len(deliveries)
        successful = len([d for d in deliveries if d.get("success", False)])
        failed = total_attempts - successful
        
        # Channel breakdown
        channel_stats = {}
        for delivery in deliveries:
            ch = delivery.get("channel", "unknown")
            if ch not in channel_stats:
                channel_stats[ch] = {"total": 0, "successful": 0, "failed": 0}
            
            channel_stats[ch]["total"] += 1
            if delivery.get("success", False):
                channel_stats[ch]["successful"] += 1
            else:
                channel_stats[ch]["failed"] += 1
        
        return {
            "timeframe": timeframe,
            "total_attempts": total_attempts,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total_attempts * 100) if total_attempts > 0 else 0,
            "channel_breakdown": channel_stats,
            "recent_deliveries": deliveries[-10:]  # Last 10 deliveries
        }
    
    def _save_templates(self) -> None:
        """Save templates to storage."""
        try:
            templates_data = {}
            for name, template in self.templates.items():
                templates_data[name] = asdict(template)
            
            with open(self.templates_file, 'w') as f:
                json.dump(templates_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save templates: {e}")
    
    def _log_delivery(self, 
                     channel: str, 
                     message: Dict[str, Any], 
                     result: NotificationResult) -> None:
        """Log notification delivery."""
        try:
            # Load existing log
            try:
                with open(self.delivery_log_file, 'r') as f:
                    delivery_log = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                delivery_log = {"deliveries": []}
            
            # Add new delivery record
            delivery_record = {
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ'),
                "channel": channel,
                "success": result.success,
                "message_id": result.message_id,
                "error_message": result.error_message,
                "change_id": message.get("change_id"),
                "schema_target": message.get("schema_target"),
                "notification_type": message.get("type")
            }
            
            delivery_log["deliveries"].append(delivery_record)
            
            # Keep only last 1000 records
            delivery_log["deliveries"] = delivery_log["deliveries"][-1000:]
            
            # Save log
            with open(self.delivery_log_file, 'w') as f:
                json.dump(delivery_log, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to log delivery: {e}")


def main():
    """Main entry point for notification manager testing."""
    parser = argparse.ArgumentParser(description="Notification Manager")
    parser.add_argument("--config-file", help="Configuration file")
    parser.add_argument("--storage-dir", help="Storage directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Send test notification
    test_parser = subparsers.add_parser("test", help="Send test notification")
    test_parser.add_argument("--channels", nargs="*", help="Channels to test")
    test_parser.add_argument("--template", help="Template to use")
    
    # Delivery stats
    stats_parser = subparsers.add_parser("stats", help="Show delivery statistics")
    stats_parser.add_argument("--timeframe", default="24h", choices=["1h", "24h", "7d", "30d"], help="Time period")
    stats_parser.add_argument("--channel", help="Specific channel")
    
    # List templates
    templates_parser = subparsers.add_parser("templates", help="List available templates")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Load configuration
        config = {}
        if args.config_file:
            with open(args.config_file, 'r') as f:
                config = json.load(f)
        
        manager = NotificationManager(
            config=config,
            storage_dir=args.storage_dir,
            verbose=args.verbose
        )
        
        if args.command == "test":
            test_message = {
                "type": "change_detected",
                "schema_target": "//examples/test:user_service_proto",
                "change_type": "modification",
                "repository": "oras.birb.homes/myorg/schemas",
                "impact_level": "medium",
                "created_by": "test-user",
                "breaking_changes_count": 1,
                "review_required": True,
                "review_id": "TEST_001"
            }
            
            channels = args.channels or list(manager.notifiers.keys())
            results = manager.send_notification(test_message, channels, args.template)
            
            print(f"📤 Test notification sent to {len(channels)} channels:")
            for channel, result in results.items():
                status = "✅" if result.success else "❌"
                print(f"  {status} {channel}: {result.message_id or result.error_message}")
        
        elif args.command == "stats":
            stats = manager.get_delivery_stats(args.timeframe, args.channel)
            
            print(f"📊 Notification Delivery Stats ({args.timeframe})")
            print(f"   Total attempts: {stats['total_attempts']}")
            print(f"   Successful: {stats['successful']}")
            print(f"   Failed: {stats['failed']}")
            print(f"   Success rate: {stats['success_rate']:.1f}%")
            
            if stats['channel_breakdown']:
                print(f"\n   Channel breakdown:")
                for channel, breakdown in stats['channel_breakdown'].items():
                    print(f"     {channel}: {breakdown['successful']}/{breakdown['total']} ({breakdown['successful']/breakdown['total']*100:.1f}%)")
        
        elif args.command == "templates":
            print(f"📋 Available notification templates:")
            for name, template in manager.templates.items():
                print(f"  {name}: {template.template_type} ({template.priority})")
                print(f"    Title: {template.title_template}")
                print(f"    Body: {template.body_template[:80]}...")
                print()
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
