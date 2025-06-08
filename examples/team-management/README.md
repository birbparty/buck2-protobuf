# BSR Team Management Example

This example demonstrates the BSR team management and collaboration system for scalable protobuf schema development across teams.

## Overview

This example shows how to:

- **Configure Team Hierarchies**: Set up parent-child team relationships for organizational structure
- **Manage Team Access**: Control repository access levels for different teams
- **Cross-Team Dependencies**: Enable safe collaboration between teams with different permission levels
- **Permission Validation**: Automatic permission checking during builds
- **Team-Aware Caching**: Optimize builds with team-specific caching strategies

## Example Structure

```
examples/team-management/
├── BUCK                      # Team configurations and proto libraries
├── platform_types.proto     # Platform team's core types (admin access)
├── user_service.proto       # Backend team's user service (read access to platform)
├── gateway_service.proto    # Platform team's gateway (depends on backend)
└── README.md                # This file
```

## Team Configuration

### Platform Team
- **Role**: Infrastructure and platform services
- **Members**: alice (admin), bob (maintainer), charlie (contributor)
- **Repository Access**:
  - `buf.build/company/private-schemas`: admin
  - `buf.build/company/platform-types`: admin
  - `buf.build/googleapis/googleapis`: read

### Backend Team
- **Role**: Application services and business logic
- **Members**: diana (maintainer), eve (contributor), frank (contributor)
- **Repository Access**:
  - `buf.build/company/private-schemas`: read
  - `buf.build/company/service-schemas`: write
  - `buf.build/googleapis/googleapis`: read

## Key Features Demonstrated

### 1. Team-Aware Proto Libraries

```python
enhanced_proto_library(
    name = "platform_types_proto",
    srcs = ["platform_types.proto"],
    bsr_deps = [
        "@company_private_schemas//core:types",
        "buf.build/googleapis/googleapis",
    ],
    team = "platform-team",
    team_config = ":platform_team_config",
)
```

### 2. Cross-Team Dependencies

```python
enhanced_proto_library(
    name = "gateway_service_proto",
    deps = [
        ":platform_types_proto",  # Platform team dependency
        ":user_service_proto",    # Backend team dependency
    ],
    team = "platform-team",
    team_config = ":platform_team_config",
)
```

### 3. Permission Validation

The system automatically validates that:
- Teams have appropriate access levels to BSR repositories
- Team members have sufficient roles for the requested actions
- Cross-team dependencies respect permission boundaries

### 4. Hierarchical Team Settings

```python
bsr_team_config(
    name = "platform_team_config",
    settings = {
        "auto_approve_members": False,    # Strict approval for platform team
        "require_2fa": True,             # Enhanced security
        "notification_preferences": {
            "permission_changes": True,
            "member_additions": True,
            "repository_access": True,
        },
    },
)
```

## Usage Examples

### Building with Team Context

```bash
# Build platform types (requires platform team membership)
buck2 build //examples/team-management:platform_types_proto

# Build user service (requires backend team membership)
buck2 build //examples/team-management:user_service_proto

# Build gateway service (demonstrates cross-team collaboration)
buck2 build //examples/team-management:gateway_service_proto
```

### Team Management Operations

```bash
# Create a new team
python -m tools.bsr_teams create \
    --name "frontend-team" \
    --description "Frontend development team" \
    --parent "engineering"

# Add team members
python -m tools.bsr_teams add-member \
    --team "frontend-team" \
    --username "sarah" \
    --role "maintainer" \
    --email "sarah@company.com"

# Configure repository access
python -m tools.bsr_teams add-repo \
    --team "frontend-team" \
    --repository "buf.build/company/ui-schemas" \
    --access "write"

# Validate permissions
python -m tools.bsr_teams validate \
    --team "frontend-team" \
    --repository "buf.build/company/ui-schemas" \
    --username "sarah" \
    --action "write"

# Get team information
python -m tools.bsr_teams info --team "frontend-team"
```

### Testing Against oras.birb.homes

The team management system can be tested against the `oras.birb.homes` registry:

```bash
# Configure for testing environment
export BSR_TOKEN="your_test_token"
export ORAS_REGISTRY="oras.birb.homes"

# Test team-aware caching
python -m tools.bsr_team_oras_cache \
    --team "platform-team" \
    --enable-shared-cache \
    --registry "oras.birb.homes"
```

## Proto Schema Examples

### Platform Types (platform_types.proto)

Demonstrates platform team's core infrastructure types:

- `PlatformMetadata`: Common metadata for all platform resources
- `TeamResource`: Team-aware resource ownership
- `AccessLevel`: Standardized access control levels
- `AuditInfo`: Cross-team audit logging

**Key Features**:
- Uses `buf/validate` for input validation
- Includes team ownership tracking
- Supports hierarchical access control

### User Service (user_service.proto)

Shows backend team's application service:

- Imports platform types (read-only access)
- Implements team-aware user management
- Demonstrates cross-team type usage

**Key Features**:
- Reuses platform metadata types
- Team membership management
- Audit trail integration

### Gateway Service (gateway_service.proto)

Illustrates platform team's orchestration layer:

- Depends on both platform and backend team schemas
- Implements cross-team request routing
- Provides team-aware authentication/authorization

**Key Features**:
- Cross-team dependency management
- Team-based routing logic
- Centralized audit logging

## Permission Scenarios

### Scenario 1: Platform Team Admin Access

```python
# Platform team member "alice" has admin access to platform schemas
team_manager.validate_team_permissions(
    team="platform-team",
    repository="buf.build/company/platform-schemas",
    username="alice",
    action="admin"
)  # Returns: True
```

### Scenario 2: Backend Team Read Access

```python
# Backend team member "diana" has read access to platform schemas
team_manager.validate_team_permissions(
    team="backend-team", 
    repository="buf.build/company/platform-schemas",
    username="diana",
    action="read"
)  # Returns: True

# But cannot write to platform schemas
team_manager.validate_team_permissions(
    team="backend-team",
    repository="buf.build/company/platform-schemas", 
    username="diana",
    action="write"
)  # Returns: False (initially)
```

### Scenario 3: Permission Escalation

```python
# Grant backend team write access to platform schemas
changes = {
    "repositories": {
        "buf.build/company/platform-schemas": {"access_level": "write"}
    }
}

team_manager.propagate_permission_changes("backend-team", changes)

# Now backend team can write to platform schemas
team_manager.validate_team_permissions(
    team="backend-team",
    repository="buf.build/company/platform-schemas",
    username="diana", 
    action="write"
)  # Returns: True (after permission change)
```

## Infrastructure Integration

### ORAS Registry Caching

Team configurations automatically integrate with ORAS caching:

```python
from tools.bsr_team_oras_cache import BSRTeamOrasCache

# Enable team-specific caching
team_cache = BSRTeamOrasCache(
    team="platform-team",
    registry="oras.birb.homes"
)

# Shared cache for team members
team_cache.enable_shared_cache([
    "alice", "bob", "charlie"
])
```

### Infrastructure Team Integration

For infrastructure requirements, create requests for the infrastructure team:

```bash
# Create infrastructure request
cat > ../birb-home/TEAM_MANAGEMENT_INFRASTRUCTURE_REQUEST.md << EOF
# Team Management Infrastructure Requirements

## Request
Enable team-aware BSR caching and permission validation for multi-team protobuf development.

## Requirements
1. ORAS registry with team-based access control
2. Shared caching infrastructure for team builds
3. Permission validation endpoints
4. Audit logging for team operations

## Teams
- platform-team: Infrastructure and core types
- backend-team: Application services
- frontend-team: UI and client schemas

## Expected Benefits
- Faster builds through team-specific caching
- Secure schema sharing across teams
- Centralized permission management
- Cross-team collaboration workflows
EOF
```

## Best Practices

### 1. Team Organization

- **Hierarchical Structure**: Use parent-child relationships for organizational alignment
- **Clear Responsibilities**: Each team owns specific repositories and schema domains
- **Minimal Permissions**: Grant least-privilege access levels
- **Regular Reviews**: Audit team memberships and permissions periodically

### 2. Schema Design

- **Platform Types**: Create shared types in platform-owned repositories
- **Team Boundaries**: Respect team ownership when importing schemas
- **Version Coordination**: Coordinate breaking changes across teams
- **Documentation**: Document team responsibilities and schema ownership

### 3. Permission Management

- **Role-Based Access**: Use roles rather than individual permissions
- **Graduated Access**: Start with read access, escalate as needed
- **Change Tracking**: Monitor and audit permission changes
- **Emergency Procedures**: Have escalation paths for urgent access needs

### 4. Development Workflow

- **Team-Aware Builds**: Use team configuration in all proto libraries
- **Cross-Team Dependencies**: Carefully manage dependencies between teams
- **Testing**: Validate team permissions in CI/CD pipelines
- **Monitoring**: Track team access patterns and optimize caching

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check team membership and repository access levels
2. **Build Failures**: Verify team configuration targets exist
3. **Cache Misses**: Ensure team caching is properly configured
4. **Cross-Team Conflicts**: Review dependency access permissions

### Debug Commands

```bash
# Check team configuration
python -m tools.bsr_teams info --team "platform-team"

# Validate specific permission
python -m tools.bsr_teams validate \
    --team "backend-team" \
    --repository "buf.build/company/platform-schemas" \
    --username "diana" \
    --action "read"

# List user's teams
python -c "
from tools.bsr_teams import BSRTeamManager
tm = BSRTeamManager()
print(tm.get_user_teams('diana'))
"

# Check repository access
python -c "
from tools.bsr_teams import BSRTeamManager
tm = BSRTeamManager()
print(tm.get_repository_teams('buf.build/company/platform-schemas'))
"
```

## Next Steps

1. **Extend Team Hierarchy**: Add more specialized teams (security, devops, etc.)
2. **Advanced Permissions**: Implement time-limited access and conditional permissions
3. **Integration Testing**: Set up automated testing against oras.birb.homes
4. **Monitoring**: Add metrics for team collaboration patterns
5. **Documentation**: Create team-specific schema documentation and guidelines

## Related Documentation

- [BSR Team Management Documentation](../../docs/bsr-team-management.md)
- [BSR Authentication Guide](../../docs/bsr-authentication.md)
- [Private BSR Repositories](../../docs/private-bsr-repositories.md)
- [Team Caching Optimization](../../docs/bsr-team-caching.md)
