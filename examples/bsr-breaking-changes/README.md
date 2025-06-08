# BSR Breaking Change Detection Examples

This directory demonstrates the advanced BSR breaking change detection system with team notifications, policy enforcement, and Buck2 migration planning.

## Overview

The breaking change detection system provides:

- **BSR Baseline Comparison**: Compare against published BSR repositories
- **Team Notifications**: Slack notifications with intelligent escalation
- **Policy Enforcement**: Configurable policies (warn, error, review)
- **Migration Planning**: Buck2-specific migration guidance
- **Team Coordination**: Multi-team workflow support

## Quick Start

### Basic Breaking Change Detection

```bash
# Check breaking changes against BSR baseline
buck2 run //examples/bsr-breaking-changes:check_user_api_breaking
```

### Team Notifications with Migration Planning

```bash
# Check with team notifications and migration plan
buck2 run //examples/bsr-breaking-changes:check_platform_breaking_with_teams
```

### Critical Service Protection

```bash
# Strict checking for critical services
buck2 run //examples/bsr-breaking-changes:check_critical_service_breaking
```

## Breaking Change Examples

The `user_api_v2.proto` file demonstrates common breaking changes:

### Field Changes
- **Field renaming**: `email_address` → `email` (BREAKING)
- **Field deletion**: Removed `phone` field (BREAKING)
- **Field number changes**: `metadata` field number changed (BREAKING)

### Type Changes
- **Enum to string**: `UserStatus` enum → `status` string (BREAKING)
- **Message structure**: Individual fields → `oneof` (BREAKING)

### New Requirements
- **Required fields**: New `UserProfile profile` field (BREAKING)
- **Service methods**: New `DeleteUser` RPC (potentially breaking)

### Wire Format Changes
- **New fields**: Added rate limiting fields (wire-compatible but affects clients)

## Configuration Examples

### Basic BSR Baseline Check

```python
buf_breaking(
    name = "check_api_breaking",
    srcs = [":api_proto"],
    against_repository = "buf.build/myorg/api",
    against_tag = "v1.0.0",
    breaking_policy = "warn",
)
```

### Team Coordination with Slack

```python
buf_breaking(
    name = "check_with_teams",
    srcs = [":platform_proto"],
    against_repository = "oras.birb.homes/platform/core",
    breaking_policy = "review",
    notify_teams = ["@platform-team", "@api-consumers"],
    generate_migration_plan = True,
    slack_webhook = "https://hooks.slack.com/services/...",
    escalation_hours = [1, 6, 24],
    review_required = True,
)
```

### Critical Service Protection

```python
buf_breaking(
    name = "critical_check",
    srcs = [":critical_proto"],
    against_repository = "oras.birb.homes/critical/service",
    breaking_policy = "error",  # Fail build on ANY breaking changes
    notify_teams = ["@sre-team", "@platform-team"],
    escalation_hours = [0.5, 2],  # Immediate escalation
)
```

## Migration Planning

When breaking changes are detected with `generate_migration_plan = True`, the system generates Buck2-specific guidance:

### Migration Plan Contents

1. **Breaking Changes Summary**
   - Detailed list of changes with severity
   - Impact analysis and affected files
   - Categorization (wire, source, JSON compatibility)

2. **Buck2 Build Impact**
   - Affected Buck2 targets
   - Dependency update requirements
   - Build verification steps

3. **Migration Steps**
   - Step-by-step migration instructions
   - Buck2-specific commands
   - Rollback procedures

4. **Team Coordination**
   - Teams that need to coordinate
   - Timeline and dependencies
   - Communication requirements

### Example Migration Plan

```markdown
# Breaking Change Migration Plan

## 🚨 Breaking Changes Detected
**Baseline:** oras.birb.homes/platform/core:latest
**Policy:** review
**Detected:** 2025-06-08T10:00:00Z

## Buck2 Migration Steps

### 1. Pre-Migration Preparation
Prepare for migration by backing up current state and notifying teams.
```bash
git stash push -m 'Pre-migration backup'
buck2 clean
```

### 2. Address Critical Breaking Changes
Fix critical issues that must be resolved immediately.

### 3. Update Dependencies
Update BUCK files with new dependency versions.

### 4. Verify Build
Ensure all targets build successfully after changes.
```bash
buck2 build //...
buck2 test //...
```

## Team Coordination
- @platform-team: Review breaking changes, Update local dependencies
- @api-consumers: Test consumer applications, Coordinate migration timeline
```

## Slack Notifications

### Notification Features

- **Rich Formatting**: Breaking change details with severity indicators
- **Interactive Buttons**: Acknowledge, View Migration Plan, Need Help
- **Team Coordination**: Multi-team notification support
- **Escalation**: Automatic escalation for unacknowledged critical changes

### Example Slack Message

```
🔴 Breaking Changes Detected ⚠️

Baseline: `oras.birb.homes/platform/core`
Policy: REVIEW
Issues: 3
Critical: 1

Top Breaking Changes:
🔴 `api/user.proto`: Field 'email_address' renamed to 'email'...
🟡 `api/user.proto`: Enum 'UserStatus' changed to string 'status'...
🟢 `api/user.proto`: Added new field 'profile'...

Buck2 Impact:
• 5 targets affected
• Build verification required

Migration Plan:
• Risk Level: medium
• Estimated Duration: 30-60 minutes
• Migration Steps: 4

[📋 View Migration Plan] [✅ Acknowledge] [🚨 Need Help]

Teams to Coordinate: @platform-team, @api-consumers
```

## Policy Enforcement

### Policy Types

- **`warn`**: Log breaking changes but allow build to continue
- **`error`**: Fail build immediately on any breaking changes
- **`review`**: Require manual approval before proceeding

### Escalation Timelines

Configure escalation hours for different service criticality:

- **Standard services**: `[2, 24]` - escalate after 2 hours, then 24 hours
- **Critical services**: `[0.5, 2]` - escalate after 30 minutes, then 2 hours
- **Platform services**: `[1, 6, 24]` - escalate after 1, 6, and 24 hours

## Testing and Validation

### Running Tests

```bash
# Test breaking change detection
python3 tools/bsr_breaking_change_detector.py \
  --proto-files examples/bsr-breaking-changes/user_api_v2.proto \
  --bsr-repository buf.build/myorg/userapi \
  --baseline-tag v1.0.0 \
  --output breaking_changes.json \
  --verbose

# Test Slack notifications
python3 tools/bsr_breaking_change_notifier.py \
  --webhook "https://hooks.slack.com/services/..." \
  --teams "@platform-team" \
  --test-message \
  --verbose
```

### Integration with Buck2

```bash
# Run all breaking change checks
buck2 test //examples/bsr-breaking-changes:...

# Check specific examples
buck2 run //examples/bsr-breaking-changes:check_user_api_breaking
buck2 run //examples/bsr-breaking-changes:check_platform_breaking_with_teams
buck2 run //examples/bsr-breaking-changes:check_critical_service_breaking
```

## Advanced Features

### Team Configuration

Create a `team_config.yaml` file for advanced team coordination:

```yaml
teams:
  platform-team:
    slack_channel: "#platform-alerts"
    escalation_contacts: ["@platform-lead", "@sre-lead"]
    notification_preferences:
      breaking_changes: true
      migration_plans: true
      escalations: true
  
  api-consumers:
    slack_channel: "#api-updates"  
    parent_team: "platform-team"
    dependencies: ["platform-core", "user-api"]
```

### Custom Rules Configuration

```yaml
# buf.yaml
version: v1
breaking:
  use:
    - WIRE_COMPATIBLE
    - WIRE_COMPATIBLE_STRICT
  except:
    - FIELD_SAME_DEFAULT  # Allow default value changes
    - ENUM_VALUE_NO_DELETE_UNLESS_RESERVED  # Allow enum deletions with reservation
```

### Multi-Registry Support

```python
# Support both public and private registries
buf_breaking(
    name = "check_private_registry",
    srcs = [":internal_proto"],
    against_repository = "oras.birb.homes/internal/api",
    breaking_policy = "review",
)

buf_breaking(
    name = "check_public_registry", 
    srcs = [":public_proto"],
    against_repository = "buf.build/myorg/public-api",
    breaking_policy = "warn",
)
```

## Best Practices

### 1. Gradual Migration Strategy

- Start with `warn` policy to understand impact
- Move to `review` for team coordination
- Use `error` only for critical services

### 2. Team Communication

- Configure appropriate escalation timelines
- Use descriptive team names in notifications
- Include migration guidance in notifications

### 3. Testing Integration

- Run breaking change checks in CI/CD
- Test migration plans before applying
- Use feature flags for gradual rollouts

### 4. Documentation

- Document breaking change policies
- Maintain migration runbooks
- Track schema evolution over time

## Troubleshooting

### Common Issues

**Authentication Failed**
```bash
# Set BSR token
export BSR_TOKEN="your_token_here"

# Or configure authentication
python3 tools/bsr_auth.py --setup
```

**Slack Notifications Not Sent**
```bash
# Test webhook connectivity
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Test message"}' \
  https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
```

**Buck2 Targets Not Found**
```bash
# Check Buck2 query syntax
buck2 query 'rdeps(//..., kind(proto_library, //...))'
```

### Getting Help

1. Check verbose output: `--verbose` flag
2. Review Buck2 logs: `buck2 log show`
3. Test individual components separately
4. Contact platform team via configured escalation

## Related Documentation

- [BSR Authentication Guide](../../docs/bsr-authentication.md)
- [Team Management Documentation](../../docs/bsr-team-management.md)
- [Buf Rules Reference](../../docs/buf-rules.md)
- [Buck2 Integration Guide](../../docs/buck2-integration.md)
