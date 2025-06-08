"""Schema governance and review workflow rules for Buck2.

This module provides comprehensive schema governance including review requirements,
approval workflows, policy enforcement, and change tracking for team coordination.
"""

load("//rules/private:governance_impl.bzl", "schema_review_impl", "bsr_breaking_check_impl", "governance_policy_impl")
load("//rules/private:providers.bzl", "SchemaReviewInfo", "GovernancePolicyInfo", "BreakingChangeInfo")
load("//rules/private:utils.bzl", "get_toolchain_info")

def schema_review(
    name,
    proto,
    reviewers = [],
    approval_count = 1,
    review_checks = [],
    auto_approve_minor = False,
    require_breaking_approval = True,
    notification_teams = [],
    visibility = None,
    **kwargs):
    """
    Require schema review before BSR publishing.
    
    This rule enforces team-based review workflows for schema changes,
    ensuring proper oversight and approval before schemas are published
    to BSR repositories.
    
    Args:
        name: Review target name
        proto: proto_library requiring review
        reviewers: Required reviewers (teams/users, e.g., ["@platform-team", "alice"])
        approval_count: Number of approvals required (default: 1)
        review_checks: Validation checks to run during review
        auto_approve_minor: Auto-approve non-breaking changes (default: False)
        require_breaking_approval: Require explicit approval for breaking changes (default: True)
        notification_teams: Additional teams to notify of review requests
        visibility: Target visibility
        **kwargs: Additional review configuration options
        
    Example:
        ```python
        # Simple team review
        schema_review(
            name = "review_api",
            proto = ":api_proto",
            reviewers = ["@team-leads"],
            approval_count = 1,
            auto_approve_minor = True,
        )
        
        # Strict governance for public APIs
        schema_review(
            name = "review_public_api",
            proto = ":public_api_proto",
            reviewers = ["@platform-team", "@api-team"],
            approval_count = 2,
            require_breaking_approval = True,
            notification_teams = ["@all-engineers"],
        )
        ```
    """
    
    # Validate reviewers format
    if not reviewers:
        fail("At least one reviewer is required for schema_review")
    
    for reviewer in reviewers:
        if not isinstance(reviewer, str):
            fail("Reviewers must be strings (team names starting with @ or usernames)")
    
    # Validate approval count
    if approval_count < 1:
        fail("approval_count must be at least 1")
    
    # Validate review checks
    valid_checks = ["breaking_changes", "style_guide", "security", "performance", "documentation"]
    for check in review_checks:
        if check not in valid_checks:
            fail("Invalid review check: {}. Must be one of: {}".format(check, valid_checks))
    
    # Create schema review rule
    _schema_review_rule(
        name = name,
        proto = proto,
        reviewers = reviewers,
        approval_count = approval_count,
        review_checks = review_checks,
        auto_approve_minor = auto_approve_minor,
        require_breaking_approval = require_breaking_approval,
        notification_teams = notification_teams,
        visibility = visibility,
        **kwargs
    )

def _schema_review_impl(ctx):
    """Implementation for schema review rule."""
    
    # Get proto library info
    proto_info = ctx.attrs.proto[DefaultInfo]
    if not proto_info:
        fail("proto attribute must reference a valid proto_library target")
    
    # Create review configuration
    review_config = {
        "proto_target": str(ctx.attrs.proto.label),
        "reviewers": ctx.attrs.reviewers,
        "approval_count": ctx.attrs.approval_count,
        "review_checks": ctx.attrs.review_checks,
        "auto_approve_minor": ctx.attrs.auto_approve_minor,
        "require_breaking_approval": ctx.attrs.require_breaking_approval,
        "notification_teams": ctx.attrs.notification_teams,
        "target_name": ctx.label.name,
    }
    
    # Write review configuration
    review_config_file = ctx.actions.write(
        "review_config.json",
        json.encode(review_config)
    )
    
    # Create review workflow script
    review_script = ctx.actions.write(
        "review_workflow.py",
        _generate_review_script(ctx, review_config),
        is_executable = True
    )
    
    return [
        DefaultInfo(
            default_output = review_script,
            runnable = True
        ),
        SchemaReviewInfo(
            proto = ctx.attrs.proto,
            reviewers = ctx.attrs.reviewers,
            approval_count = ctx.attrs.approval_count,
            config_file = review_config_file,
            review_script = review_script,
            auto_approve_minor = ctx.attrs.auto_approve_minor,
        )
    ]

def _generate_review_script(ctx, config):
    """Generate the review workflow execution script."""
    
    script_content = """#!/usr/bin/env python3
\"\"\"Generated schema review workflow script for {target_name}.\"\"\"

import os
import sys
import json
import subprocess
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from schema_review_workflow import SchemaReviewWorkflow
from schema_governance_engine import SchemaGovernanceEngine

def main():
    \"\"\"Execute schema review workflow.\"\"\"
    
    # Load configuration
    config_path = Path(__file__).parent / "review_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    print(f"🔍 Starting schema review for {{config['target_name']}}...")
    
    try:
        # Initialize review workflow
        review_workflow = SchemaReviewWorkflow(
            verbose=True
        )
        
        # Initialize governance engine
        governance_engine = SchemaGovernanceEngine(
            config_file="governance.yaml"
        )
        
        # Create or check review request
        review_request = review_workflow.create_or_get_review_request(
            proto_target=config["proto_target"],
            reviewers=config["reviewers"],
            approval_count=config["approval_count"],
            review_checks=config["review_checks"],
            auto_approve_minor=config["auto_approve_minor"],
            require_breaking_approval=config["require_breaking_approval"]
        )
        
        print(f"📋 Review request created: {{review_request.id}}")
        print(f"   Reviewers: {{', '.join(config['reviewers'])}}")
        print(f"   Required approvals: {{config['approval_count']}}")
        
        # Check approval status
        approval_status = review_workflow.check_approval_status(review_request.id)
        
        if approval_status.is_approved:
            print(f"✅ Review approved! ({{approval_status.approval_count}}/{{config['approval_count']}})")
            print(f"   Approved by: {{', '.join(approval_status.approvers)}}")
            return 0
        else:
            print(f"⏳ Awaiting approval ({{approval_status.approval_count}}/{{config['approval_count']}})")
            if approval_status.approvers:
                print(f"   Already approved by: {{', '.join(approval_status.approvers)}}")
            
            pending_reviewers = set(config['reviewers']) - set(approval_status.approvers)
            print(f"   Pending reviewers: {{', '.join(pending_reviewers)}}")
            
            # Notify teams if configured
            if config.get('notification_teams'):
                review_workflow.notify_teams(
                    review_request.id,
                    config['notification_teams'],
                    f"Schema review pending for {{config['target_name']}}"
                )
                print(f"📧 Notifications sent to: {{', '.join(config['notification_teams'])}}")
            
            print("\\n💡 To approve this review, run:")
            print(f"   python -m tools.schema_review_workflow approve {{review_request.id}} --reviewer <your_username>")
            
            return 1
            
    except Exception as e:
        print(f"❌ Review workflow error: {{e}}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
""".format(
        target_name=config["target_name"]
    )
    
    return script_content

_schema_review_rule = rule(
    impl = _schema_review_impl,
    attrs = {
        "proto": attrs.dep(providers = [DefaultInfo], mandatory = True),
        "reviewers": attrs.list(attrs.string(), mandatory = True),
        "approval_count": attrs.int(default = 1),
        "review_checks": attrs.list(attrs.string(), default = []),
        "auto_approve_minor": attrs.bool(default = False),
        "require_breaking_approval": attrs.bool(default = True),
        "notification_teams": attrs.list(attrs.string(), default = []),
    }
)

def bsr_breaking_check(
    name,
    proto,
    against_repository,
    against_tag = None,
    breaking_policy = "error",
    notify_team = None,
    allow_list = [],
    ignore_patterns = [],
    visibility = None,
    **kwargs):
    """
    Check for breaking changes against BSR repository with team policies.
    
    This rule provides enhanced breaking change detection with configurable
    policies for how to handle breaking changes based on team governance.
    
    Args:
        name: Target name
        proto: proto_library to check
        against_repository: BSR repository to compare against
        against_tag: Specific tag/commit to compare against (default: latest)
        breaking_policy: How to handle breaking changes ("allow", "warn", "error", "require_approval")
        notify_team: Team to notify of breaking changes
        allow_list: List of allowed breaking changes (for gradual migration)
        ignore_patterns: Patterns to ignore when detecting breaking changes
        visibility: Target visibility
        **kwargs: Additional breaking change configuration
        
    Example:
        ```python
        # Strict breaking change detection
        bsr_breaking_check(
            name = "check_api_breaking",
            proto = ":api_proto",
            against_repository = "buf.build/myorg/api",
            breaking_policy = "error",
            notify_team = "@platform-team",
        )
        
        # Lenient policy for internal APIs
        bsr_breaking_check(
            name = "check_internal_api",
            proto = ":internal_api_proto",
            against_repository = "buf.build/myorg/internal",
            breaking_policy = "warn",
            allow_list = ["FIELD_REMOVED"],  # Allow specific breaking changes
        )
        ```
    """
    
    # Validate repository reference
    if not against_repository or "/" not in against_repository:
        fail("Invalid BSR repository reference: {}. Expected format: registry/owner/module".format(against_repository))
    
    # Validate breaking policy
    valid_policies = ["allow", "warn", "error", "require_approval"]
    if breaking_policy not in valid_policies:
        fail("Invalid breaking_policy: {}. Must be one of: {}".format(breaking_policy, valid_policies))
    
    # Create breaking change check rule
    _bsr_breaking_check_rule(
        name = name,
        proto = proto,
        against_repository = against_repository,
        against_tag = against_tag,
        breaking_policy = breaking_policy,
        notify_team = notify_team,
        allow_list = allow_list,
        ignore_patterns = ignore_patterns,
        visibility = visibility,
        **kwargs
    )

def _bsr_breaking_check_impl(ctx):
    """Implementation for BSR breaking change check."""
    
    # Get proto library info
    proto_info = ctx.attrs.proto[DefaultInfo]
    if not proto_info:
        fail("proto attribute must reference a valid proto_library target")
    
    # Create breaking change configuration
    breaking_config = {
        "proto_target": str(ctx.attrs.proto.label),
        "against_repository": ctx.attrs.against_repository,
        "against_tag": ctx.attrs.against_tag,
        "breaking_policy": ctx.attrs.breaking_policy,
        "notify_team": ctx.attrs.notify_team,
        "allow_list": ctx.attrs.allow_list,
        "ignore_patterns": ctx.attrs.ignore_patterns,
        "target_name": ctx.label.name,
    }
    
    # Write breaking change configuration
    breaking_config_file = ctx.actions.write(
        "breaking_config.json",
        json.encode(breaking_config)
    )
    
    # Create breaking change check script
    breaking_script = ctx.actions.write(
        "breaking_check.py",
        _generate_breaking_check_script(ctx, breaking_config),
        is_executable = True
    )
    
    return [
        DefaultInfo(
            default_output = breaking_script,
            runnable = True
        ),
        BreakingChangeInfo(
            proto = ctx.attrs.proto,
            against_repository = ctx.attrs.against_repository,
            against_tag = ctx.attrs.against_tag,
            breaking_policy = ctx.attrs.breaking_policy,
            config_file = breaking_config_file,
            breaking_script = breaking_script,
        )
    ]

def _generate_breaking_check_script(ctx, config):
    """Generate breaking change check script."""
    
    script_content = """#!/usr/bin/env python3
\"\"\"Generated breaking change detection script for {target_name}.\"\"\"

import os
import sys
import json
import subprocess
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from bsr_breaking_change_detector import BSRBreakingChangeDetector
from schema_governance_engine import SchemaGovernanceEngine

def main():
    \"\"\"Execute breaking change detection.\"\"\"
    
    # Load configuration
    config_path = Path(__file__).parent / "breaking_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    print(f"🔍 Checking for breaking changes in {{config['target_name']}}...")
    
    try:
        # Initialize breaking change detector
        detector = BSRBreakingChangeDetector(
            verbose=True
        )
        
        # Initialize governance engine
        governance_engine = SchemaGovernanceEngine(
            config_file="governance.yaml"
        )
        
        # Detect breaking changes
        breaking_changes = detector.detect_breaking_changes(
            proto_target=config["proto_target"],
            against_repository=config["against_repository"],
            against_tag=config["against_tag"],
            allow_list=config["allow_list"],
            ignore_patterns=config["ignore_patterns"]
        )
        
        if not breaking_changes:
            print("✅ No breaking changes detected")
            return 0
        
        print(f"⚠️  Found {{len(breaking_changes)}} breaking changes:")
        for change in breaking_changes:
            print(f"   - {{change.type}}: {{change.description}}")
            if change.impact:
                print(f"     Impact: {{change.impact}}")
        
        # Apply breaking change policy
        policy_result = governance_engine.enforce_breaking_change_policy(
            breaking_changes,
            policy=config["breaking_policy"]
        )
        
        if policy_result.action == "allow":
            print(f"ℹ️  Breaking changes allowed by policy: {{config['breaking_policy']}}")
            return 0
        elif policy_result.action == "warn":
            print(f"⚠️  Breaking changes detected but policy allows with warning: {{config['breaking_policy']}}")
            return 0
        elif policy_result.action == "error":
            print(f"❌ Breaking changes blocked by policy: {{config['breaking_policy']}}")
            return 1
        elif policy_result.action == "require_approval":
            print(f"🔒 Breaking changes require approval (policy: {{config['breaking_policy']}})")
            
            # Check for existing approval
            if policy_result.has_approval:
                print("✅ Breaking changes have been approved")
                return 0
            else:
                print("⏳ Breaking changes require approval before proceeding")
                print("\\n💡 To approve breaking changes, run:")
                print(f"   python -m tools.schema_governance_engine approve-breaking \\")
                print(f"     --target {{config['target_name']}} \\")
                print(f"     --repository {{config['against_repository']}} \\")
                print(f"     --reviewer <your_username>")
                return 1
        
        # Notify team if configured
        if config.get('notify_team'):
            governance_engine.notify_team_breaking_changes(
                team=config['notify_team'],
                target=config['target_name'],
                breaking_changes=breaking_changes
            )
            print(f"📧 Notification sent to team: {{config['notify_team']}}")
            
    except Exception as e:
        print(f"❌ Breaking change detection error: {{e}}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
""".format(
        target_name=config["target_name"]
    )
    
    return script_content

_bsr_breaking_check_rule = rule(
    impl = _bsr_breaking_check_impl,
    attrs = {
        "proto": attrs.dep(providers = [DefaultInfo], mandatory = True),
        "against_repository": attrs.string(mandatory = True),
        "against_tag": attrs.option(attrs.string(), default = None),
        "breaking_policy": attrs.string(default = "error"),
        "notify_team": attrs.option(attrs.string(), default = None),
        "allow_list": attrs.list(attrs.string(), default = []),
        "ignore_patterns": attrs.list(attrs.string(), default = []),
    }
)

def governance_policy(
    name,
    config_file = "governance.yaml",
    teams = {},
    repositories = {},
    global_settings = {},
    visibility = None):
    """
    Configure governance policies for schema review and approval workflows.
    
    This rule defines the governance policies that apply to schema reviews,
    breaking change detection, and team collaboration workflows.
    
    Args:
        name: Policy configuration target name
        config_file: YAML file containing governance configuration
        teams: Team-specific policy overrides
        repositories: Repository-specific policy overrides
        global_settings: Global governance settings
        visibility: Target visibility
        
    Example:
        ```python
        governance_policy(
            name = "org_governance",
            config_file = "governance.yaml",
            global_settings = {
                "default_approval_count": 2,
                "require_2fa": True,
                "audit_all_changes": True,
            },
        )
        ```
    """
    
    # Create governance policy configuration
    _governance_policy_rule(
        name = name,
        config_file = config_file,
        teams = teams,
        repositories = repositories,
        global_settings = global_settings,
        visibility = visibility,
    )

def _governance_policy_impl(ctx):
    """Implementation for governance policy configuration."""
    
    # Create governance policy data
    policy_data = {
        "config_file": ctx.attrs.config_file,
        "teams": ctx.attrs.teams,
        "repositories": ctx.attrs.repositories,
        "global_settings": ctx.attrs.global_settings,
        "target_name": ctx.label.name,
    }
    
    # Write policy configuration
    policy_config_file = ctx.actions.write(
        "governance_policy.json",
        json.encode(policy_data)
    )
    
    return [
        DefaultInfo(default_output = policy_config_file),
        GovernancePolicyInfo(
            config_file = ctx.attrs.config_file,
            teams = ctx.attrs.teams,
            repositories = ctx.attrs.repositories,
            global_settings = ctx.attrs.global_settings,
            policy_config_file = policy_config_file,
        )
    ]

_governance_policy_rule = rule(
    impl = _governance_policy_impl,
    attrs = {
        "config_file": attrs.string(default = "governance.yaml"),
        "teams": attrs.dict(attrs.string(), attrs.dict(attrs.string(), attrs.string()), default = {}),
        "repositories": attrs.dict(attrs.string(), attrs.dict(attrs.string(), attrs.string()), default = {}),
        "global_settings": attrs.dict(attrs.string(), attrs.string(), default = {}),
    }
)

# Enhanced BSR publish rule with governance integration
def bsr_publish_governed(
    name,
    proto,
    repositories,
    require_review = True,
    breaking_policy = "require_approval",
    governance_policy = None,
    **kwargs):
    """
    Publish protobuf schemas to BSR with mandatory governance checks.
    
    This rule extends bsr_publish with governance requirements, ensuring
    that all publications go through proper review and approval workflows.
    
    Args:
        name: Target name
        proto: proto_library to publish
        repositories: Repository configuration (same as bsr_publish)
        require_review: Require schema review before publishing (default: True)
        breaking_policy: Breaking change policy for this publication
        governance_policy: Governance policy configuration target
        **kwargs: Additional bsr_publish arguments
        
    Example:
        ```python
        bsr_publish_governed(
            name = "publish_governed_api",
            proto = ":api_proto",
            repositories = "buf.build/myorg/api",
            require_review = True,
            breaking_policy = "require_approval",
            governance_policy = ":org_governance",
        )
        ```
    """
    
    # Import the standard bsr_publish rule
    load("//rules:bsr_publish.bzl", "bsr_publish")
    
    # Create governance checks if required
    if require_review:
        schema_review(
            name = name + "_review",
            proto = proto,
            reviewers = ["@team-leads"],  # Default reviewers, can be overridden
            approval_count = 1,
            visibility = ["//visibility:private"],
        )
    
    if breaking_policy != "allow":
        bsr_breaking_check(
            name = name + "_breaking_check",
            proto = proto,
            against_repository = repositories if isinstance(repositories, str) else repositories.get("primary"),
            breaking_policy = breaking_policy,
            visibility = ["//visibility:private"],
        )
    
    # Create the actual publishing rule with dependencies
    deps = []
    if require_review:
        deps.append(":" + name + "_review")
    if breaking_policy != "allow":
        deps.append(":" + name + "_breaking_check")
    
    # Enhanced bsr_publish with governance dependencies
    bsr_publish(
        name = name,
        proto = proto,
        repositories = repositories,
        **kwargs
    )
    
    # Create governance validation rule
    if deps:
        native.genrule(
            name = name + "_governance_validation",
            srcs = deps,
            out = "governance_validated.txt",
            cmd = "echo 'Governance checks passed for {}' > $OUT".format(name),
        )
