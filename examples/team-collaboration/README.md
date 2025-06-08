# Team Collaboration Tools

This directory contains comprehensive tools and examples for enabling seamless team collaboration when working with protobuf schemas in Buck2. These tools provide advanced change tracking, impact analysis, multi-platform notifications, and performance optimization capabilities.

## 🚀 Quick Start

### 1. Configure Notifications

Create a notification configuration file based on the example:

```bash
cp examples/team-collaboration/notification_config.json team-notifications.json
# Edit with your actual webhook URLs and credentials
```

### 2. Track Schema Changes

```bash
# Track a schema change
python3 -m tools.bsr_change_tracker track \
  --target "//examples/user:user_service_proto" \
  --type "modification" \
  --repository "oras.birb.homes/myorg/schemas" \
  --created-by "developer@company.com" \
  --description "Added new user status field"

# View change history
python3 -m tools.bsr_change_tracker history --team "platform-team"

# Generate team change report
python3 -m tools.bsr_change_tracker report --timeframe "7d" --team "platform-team"
```

### 3. Send Notifications

```bash
# Test notifications
python3 -m tools.notification_manager test \
  --config-file team-notifications.json \
  --channels slack teams email

# View delivery statistics
python3 -m tools.notification_manager stats --timeframe "24h"
```

### 4. Analyze Dependencies

```bash
# Register a service dependency
python3 -m tools.dependency_impact_analyzer register-dependency \
  --schema "//examples/user:user_service_proto" \
  --service "user-api-service" \
  --repository "github.com/company/user-api" \
  --strength "critical" \
  --team "platform-team"

# Analyze dependency graph
python3 -m tools.dependency_impact_analyzer analyze \
  --schema "//examples/user:user_service_proto"

# Generate migration plan
python3 -m tools.dependency_impact_analyzer migration-plan \
  --change-id "CHG_001" \
  --schema "//examples/user:user_service_proto" \
  --output migration-plan.json
```

### 5. Optimize Team Performance

```bash
# Analyze team usage patterns
python3 -m tools.team_performance_optimizer analyze-patterns \
  --team "platform-team" \
  --period "7d"

# Get cache optimization strategy
python3 -m tools.team_performance_optimizer optimize-cache \
  --team "platform-team"

# Generate optimization report
python3 -m tools.team_performance_optimizer optimization-report \
  --team "platform-team" \
  --output team-optimization.json
```

## 📋 Components Overview

### 1. BSR Change Tracker (`tools/bsr_change_tracker.py`)

**Purpose**: Comprehensive change tracking system with team context and impact analysis.

**Key Features**:
- Track schema changes with team ownership
- Automatic breaking change detection
- Impact analysis across teams and services
- Review workflow integration
- Audit logging and compliance

**Example Usage**:
```bash
# Track a breaking change
python3 -m tools.bsr_change_tracker track \
  --target "//api:user_proto" \
  --type "modification" \
  --repository "main-repo" \
  --created-by "dev@company.com" \
  --commit "abc123" \
  --description "Removed deprecated field"

# Analyze change impact
python3 -m tools.bsr_change_tracker analyze CHG_1234567890_abc123
```

### 2. Notification Manager (`tools/notification_manager.py`)

**Purpose**: Multi-platform notification system for schema changes and team coordination.

**Supported Platforms**:
- **Slack**: Rich message formatting with attachments
- **Microsoft Teams**: Adaptive cards with structured data
- **Email**: Detailed HTML/text emails with full context
- **Webhooks**: Generic HTTP notifications for custom integrations

**Key Features**:
- Template-based message formatting
- Platform-specific optimizations
- Delivery tracking and statistics
- Retry logic and error handling

**Configuration Example**:
```json
{
  "slack": {
    "enabled": true,
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK",
    "channel": "#schema-changes",
    "username": "Schema Bot"
  },
  "teams": {
    "enabled": true,
    "webhook_url": "https://outlook.office.com/webhook/YOUR-TEAMS-WEBHOOK"
  },
  "email": {
    "enabled": true,
    "smtp_server": "smtp.company.com",
    "from_address": "schema-bot@company.com",
    "default_recipients": ["platform-team@company.com"]
  }
}
```

### 3. Dependency Impact Analyzer (`tools/dependency_impact_analyzer.py`)

**Purpose**: Advanced dependency analysis for cross-team coordination and migration planning.

**Key Features**:
- Service dependency registration and tracking
- Cross-team dependency analysis
- Migration planning with phased rollouts
- Risk assessment and mitigation strategies
- Rollback planning and coordination

**Data Models**:
- **ServiceDependency**: Service relationships to schemas
- **DependencyGraph**: Complete dependency visualization
- **TeamImpact**: Team-specific impact analysis
- **MigrationPlan**: Comprehensive migration strategy

### 4. Team Performance Optimizer (`tools/team_performance_optimizer.py`)

**Purpose**: Team-specific performance optimization with usage pattern analysis.

**Key Features**:
- Usage pattern analysis per team
- Cache strategy optimization
- Build performance recommendations
- Workflow improvement suggestions
- Implementation roadmaps

**Optimization Areas**:
- **Caching**: Strategy optimization (aggressive/balanced/conservative)
- **Build Performance**: Parallel builds, dependency optimization
- **Automation**: CI/CD optimization, automated testing
- **Workflow**: Team-specific process improvements

## 🔧 Integration Examples

### Buck2 Integration

Add team collaboration to your Buck2 build:

```python
# In your BUCK file
load("//rules:team_collaboration.bzl", "team_change_tracking")

team_change_tracking(
    name = "user_service_tracking",
    proto_target = ":user_service_proto",
    team_owner = "platform-team",
    notification_config = "team-notifications.json",
    dependency_analysis = True,
)
```

### CI/CD Integration

Add to your GitHub Actions workflow:

```yaml
- name: Track Schema Changes
  run: |
    python3 -m tools.bsr_change_tracker track \
      --target "${{ matrix.proto_target }}" \
      --type "modification" \
      --repository "${{ github.repository }}" \
      --created-by "${{ github.actor }}" \
      --commit "${{ github.sha }}" \
      --branch "${{ github.ref_name }}"

- name: Analyze Impact
  run: |
    python3 -m tools.dependency_impact_analyzer affected-services \
      --schema "${{ matrix.proto_target }}"
```

### Monitoring Integration

Set up performance monitoring:

```bash
# Daily performance analysis
0 8 * * * python3 -m tools.team_performance_optimizer optimization-report \
  --team "platform-team" \
  --output "/var/reports/team-performance-$(date +%Y%m%d).json"

# Weekly dependency analysis
0 9 * * 1 python3 -m tools.dependency_impact_analyzer analyze \
  --schema "//api:core_protos"
```

## 📊 Reporting and Analytics

### Change Reports

Generate comprehensive change reports:

```bash
# Team-specific change report
python3 -m tools.bsr_change_tracker report \
  --timeframe "30d" \
  --team "platform-team" \
  --output platform-team-changes.json

# Cross-team impact report
python3 -m tools.dependency_impact_analyzer team-impacts \
  --schema "//core:api_proto"
```

### Performance Analytics

Track team performance over time:

```bash
# Usage pattern analysis
python3 -m tools.team_performance_optimizer analyze-patterns \
  --team "platform-team" \
  --period "30d"

# Optimization tracking
python3 -m tools.team_performance_optimizer workflow-improvements \
  --team "platform-team"
```

### Notification Analytics

Monitor notification delivery:

```bash
# Delivery statistics
python3 -m tools.notification_manager stats \
  --timeframe "7d" \
  --channel "slack"

# Template performance
python3 -m tools.notification_manager templates
```

## 🛠️ Configuration

### Team Configuration

Set up team-specific configurations:

```bash
# Configure team notifications
python3 -m tools.bsr_change_tracker configure-notifications \
  --team "platform-team" \
  --config-file team-notification-rules.json

# Register team services
python3 -m tools.dependency_impact_analyzer register-service \
  --name "user-api-service" \
  --info-file service-info.json
```

### Notification Templates

Customize notification templates:

```json
{
  "breaking_change": {
    "template_type": "breaking_change",
    "title_template": "🚨 Breaking Change: {schema_target}",
    "body_template": "Breaking changes in {schema_target}!\n{breaking_changes_count} changes detected.",
    "priority": "critical"
  }
}
```

## 📈 Best Practices

### Change Tracking

1. **Always track changes**: Include tracking in your development workflow
2. **Provide context**: Add meaningful descriptions and commit information
3. **Review regularly**: Use team reports to identify patterns
4. **Act on insights**: Implement suggested improvements

### Dependency Management

1. **Register all dependencies**: Maintain accurate service catalogs
2. **Classify criticality**: Use appropriate dependency strengths
3. **Plan migrations**: Use generated migration plans
4. **Test coordination**: Validate cross-team changes

### Notifications

1. **Configure appropriately**: Match notification urgency to change impact
2. **Avoid spam**: Use filtering and escalation rules
3. **Monitor delivery**: Track notification effectiveness
4. **Iterate on templates**: Improve message clarity over time

### Performance Optimization

1. **Analyze regularly**: Run performance analysis weekly
2. **Implement incrementally**: Follow generated roadmaps
3. **Measure impact**: Track improvement metrics
4. **Share learnings**: Propagate successful optimizations

## 🔍 Troubleshooting

### Common Issues

**Notifications not delivered**:
```bash
# Check configuration
python3 -m tools.notification_manager test --channels slack

# Verify credentials
python3 -m tools.notification_manager stats --channel slack
```

**Missing dependencies**:
```bash
# Verify service registration
python3 -m tools.dependency_impact_analyzer register-service \
  --name "my-service" \
  --info-file service-info.json
```

**Performance issues**:
```bash
# Analyze usage patterns
python3 -m tools.team_performance_optimizer analyze-patterns \
  --team "my-team"
```

### Debug Mode

Enable verbose logging:

```bash
# All tools support verbose mode
python3 -m tools.bsr_change_tracker --verbose track ...
python3 -m tools.notification_manager --verbose test ...
python3 -m tools.dependency_impact_analyzer --verbose analyze ...
python3 -m tools.team_performance_optimizer --verbose optimize-cache ...
```

## 🤝 Contributing

See the main [Contributing Guide](../../docs/contributing.md) for general guidelines.

### Team Collaboration Specific

1. Test with real team scenarios
2. Validate notification delivery
3. Verify dependency analysis accuracy
4. Check performance optimization recommendations

### Adding New Features

1. Follow existing patterns in the codebase
2. Add comprehensive tests
3. Update documentation
4. Consider cross-team impacts

## 📚 Additional Resources

- [BSR Team Management](../../docs/bsr-team-management.md)
- [Performance Monitoring](../../docs/performance.md)
- [Migration Guide](../../docs/migration-guide.md)
- [Troubleshooting](../../docs/troubleshooting.md)

---

For questions or support, please refer to the main project documentation or create an issue in the repository.
