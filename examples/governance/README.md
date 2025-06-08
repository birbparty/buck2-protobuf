# Schema Governance Examples

This directory demonstrates the comprehensive schema governance framework for Buck2 Protobuf, including review workflows, approval processes, policy enforcement, and change tracking.

## Overview

The schema governance framework provides:

- **Schema Review Workflows**: Team-based review and approval processes
- **Breaking Change Detection**: Automated detection with impact analysis
- **Policy Enforcement**: Configurable governance policies for different teams and repositories
- **Audit Trails**: Comprehensive tracking for compliance and accountability
- **Team Collaboration**: Multi-team coordination for schema evolution

## Example Structure

```
examples/governance/
├── README.md                    # This file
├── BUCK                        # Buck2 build configuration
├── governance.yaml             # Governance policy configuration
├── public-api/                 # Public API with strict governance
├── internal-api/               # Internal API with moderate governance
├── experimental/               # Experimental API with relaxed governance
└── workflows/                  # Workflow examples and CI/CD integration
```

## Key Features Demonstrated

### 1. Multi-Level Governance

- **Public APIs**: Strict review requirements with multiple approvers
- **Internal APIs**: Moderate governance for team coordination
- **Experimental APIs**: Flexible policies for rapid iteration

### 2. Breaking Change Management

- **Detection**: Automated breaking change detection using buf CLI
- **Policies**: Configurable responses (allow/warn/error/require_approval)
- **Impact Analysis**: Assessment of migration complexity and affected components
- **Migration Guides**: Automated generation of migration documentation

### 3. Team-Based Workflows

- **Review Assignments**: Automatic assignment based on team membership
- **Approval Tracking**: Multi-stage approval processes
- **Notifications**: Team-aware notification systems
- **Permission Validation**: Team-based access control

### 4. Audit and Compliance

- **Change Tracking**: Comprehensive audit trails for all governance actions
- **Compliance Reports**: Automated generation of compliance documentation
- **Policy Violations**: Detection and reporting of policy violations
- **Accountability**: Clear ownership and approval tracking

## Quick Start

### 1. Configure Governance Policies

```yaml
# governance.yaml
schema_governance:
  review_policies:
    public_apis:
      required_reviewers: ["@platform-team", "@api-team"]
      approval_count: 2
      require_breaking_approval: true
      
  breaking_change_policies:
    "buf.build/myorg/public-api": "require_approval"
    "buf.build/myorg/internal-api": "warn"
    default: "error"
```

### 2. Define Governed Proto Libraries

```python
# BUCK
load("//rules:governance.bzl", "schema_review", "bsr_breaking_check", "bsr_publish_governed")

schema_review(
    name = "review_public_api",
    proto = ":public_api_proto",
    reviewers = ["@platform-team", "@api-team"],
    approval_count = 2,
    require_breaking_approval = True,
)

bsr_breaking_check(
    name = "check_public_api_breaking",
    proto = ":public_api_proto",
    against_repository = "buf.build/myorg/public-api",
    breaking_policy = "require_approval",
    notify_team = "@platform-team",
)

bsr_publish_governed(
    name = "publish_public_api",
    proto = ":public_api_proto",
    repositories = "buf.build/myorg/public-api",
    require_review = True,
    breaking_policy = "require_approval",
)
```

### 3. Team-Aware Building

```bash
# Build with governance checks
buck2 build //examples/governance/public-api:review_public_api

# Check for breaking changes
buck2 run //examples/governance/public-api:check_public_api_breaking

# Publish with governance (after approvals)
buck2 run //examples/governance/public-api:publish_public_api
```

### 4. Review Workflow Operations

```bash
# Create review request
python -m tools.schema_review_workflow create \
    --target "//examples/governance/public-api:public_api_proto" \
    --reviewers "@platform-team" "@api-team" \
    --approval-count 2

# Approve review
python -m tools.schema_review_workflow approve <review_id> \
    --reviewer alice \
    --comment "LGTM - API design follows platform standards"

# Check review status
python -m tools.schema_review_workflow status <review_id>
```

### 5. Breaking Change Analysis

```bash
# Detect breaking changes
python -m tools.bsr_breaking_change_detector detect \
    --target "//examples/governance/public-api:public_api_proto" \
    --against "buf.build/myorg/public-api"

# Analyze impact
python -m tools.bsr_breaking_change_detector analyze \
    --changes-file breaking_changes.json \
    --repository "buf.build/myorg/public-api"

# Generate migration guide
python -m tools.bsr_breaking_change_detector guide \
    --changes-file breaking_changes.json \
    --repository "buf.build/myorg/public-api" \
    --output migration_guide.md
```

### 6. Governance Engine Operations

```bash
# Approve schema review
python -m tools.schema_governance_engine approve \
    --target "//examples/governance/public-api:public_api_proto" \
    --reviewer alice

# Approve breaking changes
python -m tools.schema_governance_engine approve-breaking \
    --target "//examples/governance/public-api:public_api_proto" \
    --repository "buf.build/myorg/public-api" \
    --reviewer alice

# Generate compliance report
python -m tools.schema_governance_engine report \
    --timeframe 30d \
    --output compliance_report.json
```

## Example Scenarios

### Scenario 1: Public API Review Process

1. **Developer submits changes** to public API schema
2. **Governance system** automatically creates review request
3. **Platform and API teams** receive notifications
4. **Reviewers** examine changes and provide feedback
5. **Breaking change detection** runs automatically
6. **Approval required** for any breaking changes
7. **Publication** proceeds only after all approvals

### Scenario 2: Breaking Change Management

1. **Breaking change detected** during comparison
2. **Impact analysis** determines high-risk change
3. **Migration guide** generated automatically
4. **Team notifications** sent to affected consumers
5. **Approval workflow** initiated for breaking changes
6. **Publication blocked** until explicit approval
7. **Audit trail** records all governance decisions

### Scenario 3: Team Collaboration

1. **Cross-team dependency** requires schema change
2. **Multiple teams** involved in review process
3. **Permission validation** ensures authorized reviewers
4. **Staged approvals** coordinate between teams
5. **Notification system** keeps all teams informed
6. **Change tracking** provides accountability
7. **Compliance reporting** satisfies audit requirements

## Testing Against oras.birb.homes

The governance framework supports testing against the ORAS registry:

```bash
# Configure for ORAS testing
export BSR_TOKEN="your_test_token"
export ORAS_REGISTRY="oras.birb.homes"

# Test governance with ORAS
buck2 build //examples/governance:all \
    --config=oras.test=true

# Test breaking change detection against ORAS
python -m tools.bsr_breaking_change_detector detect \
    --target "//examples/governance/public-api:public_api_proto" \
    --against "oras.birb.homes/myorg/public-api"
```

## Infrastructure Integration

For additional infrastructure requirements, create requests for the infrastructure team:

```bash
# Create infrastructure request
cat > $HOME/git/birb-home/GOVERNANCE_INFRASTRUCTURE_REQUEST.md << EOF
# Schema Governance Infrastructure Requirements

## Request
Implement comprehensive schema governance infrastructure for multi-team protobuf development.

## Requirements
1. ORAS registry with team-based access control
2. Review workflow integration with notification systems
3. Breaking change detection and impact analysis
4. Audit trail storage and compliance reporting
5. CI/CD integration for automated governance

## Teams
- platform-team: Infrastructure and governance oversight
- api-team: Public API design and standards
- security-team: Security review and compliance
- All development teams: Schema consumers and contributors

## Expected Benefits
- Systematic schema review and approval processes
- Automated breaking change detection and management
- Comprehensive audit trails for compliance
- Team coordination for schema evolution
- Risk mitigation for schema changes
EOF
```

## Best Practices

### 1. Policy Configuration

- **Start conservative**: Begin with strict policies and relax as teams adapt
- **Team-specific policies**: Customize governance for different team needs
- **Repository classification**: Clearly categorize repositories by governance level
- **Regular review**: Periodically review and update governance policies

### 2. Review Workflows

- **Clear responsibilities**: Define clear reviewer assignments and expectations
- **Timely reviews**: Set reasonable approval timeouts and escalation procedures
- **Constructive feedback**: Encourage detailed review comments and suggestions
- **Documentation**: Maintain clear documentation for governance processes

### 3. Breaking Change Management

- **Early detection**: Integrate breaking change detection into development workflow
- **Impact assessment**: Always analyze the impact of breaking changes
- **Migration support**: Provide clear migration guides and tooling
- **Communication**: Proactively communicate breaking changes to affected teams

### 4. Team Collaboration

- **Cross-team coordination**: Establish clear processes for cross-team dependencies
- **Notification management**: Configure notifications to avoid spam while ensuring awareness
- **Permission management**: Regularly review and update team permissions
- **Training**: Provide training on governance processes and tools

## Advanced Features

### Custom Validation Rules

```python
# Add custom validation to governance checks
schema_review(
    name = "review_with_custom_validation",
    proto = ":api_proto",
    reviewers = ["@platform-team"],
    review_checks = ["breaking_changes", "style_guide", "custom_security"],
)
```

### Emergency Override Procedures

```bash
# Emergency override for critical fixes
python -m tools.schema_governance_engine approve \
    --target "//examples/governance/public-api:public_api_proto" \
    --reviewer platform-admin \
    --emergency-override \
    --justification "Critical security fix for CVE-2024-XXXX"
```

### Batch Operations

```python
# Batch publishing with coordinated governance
bsr_publish_multiple(
    name = "publish_all_governed_apis",
    targets = [
        ":public_api_proto",
        ":internal_api_proto",
        ":experimental_api_proto"
    ],
    repositories = {
        "primary": "buf.build/myorg/apis",
        "backup": "oras.birb.homes/myorg/apis"
    },
    require_review = True,
    breaking_policy = "require_approval",
)
```

## Troubleshooting

### Common Issues

1. **Review timeout**: Increase approval timeout or add additional reviewers
2. **Permission denied**: Verify team membership and repository access
3. **Breaking change conflicts**: Use allow lists for gradual migration
4. **Policy violations**: Review governance configuration and team settings

### Debug Commands

```bash
# Check governance configuration
python -c "
from tools.schema_governance_engine import SchemaGovernanceEngine
engine = SchemaGovernanceEngine('governance.yaml')
print(engine.config)
"

# Validate team permissions
python -m tools.bsr_teams validate \
    --team platform-team \
    --repository "buf.build/myorg/public-api" \
    --username alice \
    --action write

# Review audit trail
python -m tools.schema_governance_engine report \
    --timeframe 7d \
    --team platform-team
```

## Related Documentation

- [BSR Team Management](../team-management/README.md)
- [Breaking Change Detection](../../docs/breaking-changes.md)
- [Review Workflows](../../docs/review-workflows.md)
- [Compliance and Auditing](../../docs/compliance.md)
- [Governance Configuration](../../docs/governance-config.md)

---

This governance framework transforms ad-hoc schema changes into systematic, collaborative processes that scale with team growth and organizational needs. 🏛️
