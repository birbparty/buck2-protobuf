# BSR Team Management and Collaboration

This document describes the BSR team management system that enables scalable collaboration on protobuf schemas with team-based access control, permission management, and workflow integration.

## Overview

The BSR team management system provides:

- **Team Access Configuration**: Centralized team permission management for BSR repositories
- **Collaborator Management**: Role-based access control with hierarchical teams
- **Repository Organization**: Team-specific schema organization patterns
- **Workflow Integration**: Team-aware Buck2 builds and caching optimization
- **Permission Propagation**: Real-time permission change handling across teams

## Key Components

### 1. Team Management Core (`tools/bsr_teams.py`)

The central team management system provides:

```python
from tools.bsr_teams import BSRTeamManager

# Initialize team manager
team_manager = BSRTeamManager(verbose=True)

# Create a team
team = team_manager.create_team(
    name="platform-team",
    description="Platform infrastructure team",
    parent_team="engineering"
)

# Add team members
team_manager.manage_team_members(
    team="platform-team",
    members=[
        {"username": "alice", "role": "admin"},
        {"username": "bob", "role": "maintainer"}
    ],
    action="add"
)

# Configure repository access
team_manager.configure_team_access(
    team="platform-team",
    repositories=["buf.build/company/platform-schemas"],
    access_level="admin"
)
```

### 2. Buck2 Integration (`rules/bsr.bzl`)

Team-aware protobuf rules for Buck2:

```python
# Configure team settings
bsr_team_config(
    name = "platform_team_config",
    team = "platform-team",
    members = {
        "alice": "admin",
        "bob": "maintainer",
    },
    repositories = {
        "buf.build/company/platform-schemas": "admin",
    },
)

# Team-aware proto library
enhanced_proto_library(
    name = "api_proto",
    srcs = ["api.proto"],
    bsr_deps = ["@company_schemas//platform:types"],
    team = "platform-team",
    team_config = ":platform_team_config",
)
```

### 3. Team Caching Integration

Automatic integration with team caching for optimized builds:

```python
from tools.bsr_team_oras_cache import BSRTeamOrasCache

# Team caching automatically optimizes based on usage patterns
team_cache = BSRTeamOrasCache(team="platform-team", ...)
team_cache.enable_shared_cache(["alice", "bob", "charlie"])
```

## Team Structure and Roles

### Role Hierarchy

1. **Viewer**: Read-only access to team repositories
2. **Contributor**: Read and write access to assigned repositories
3. **Maintainer**: Full access to team repositories, can manage contributors
4. **Admin**: Full team management including member and permission management

### Permission Model

Permissions are enforced at multiple levels:

- **Repository Level**: Each repository has a default access level for the team
- **Member Level**: Individual members can have role overrides per repository
- **Team Level**: Team-wide settings and defaults
- **Hierarchical**: Child teams inherit permissions from parent teams

### Team Organization

```yaml
# Example team hierarchy
engineering:
  child_teams:
    - platform-team
    - backend-team
    - frontend-team
  
platform-team:
  parent_team: engineering
  members:
    alice: admin
    bob: maintainer
    charlie: contributor
  repositories:
    "buf.build/company/platform-schemas": admin
    "buf.build/company/core-types": admin
```

## Repository Access Control

### Private Repository Configuration

```python
# Configure private BSR repository
bsr_repository(
    name = "company_private_schemas",
    repository = "buf.build/company/private-schemas",
    auth_method = "service_account",
    teams = ["@platform-team", "@backend-team"],
    access_level = "read",
    service_account_file = "service_account.json",
)
```

### Team-Specific Access

Teams can have different access levels to the same repository:

```python
# Platform team has admin access
bsr_team_config(
    name = "platform_team_config",
    repositories = {
        "buf.build/company/schemas": "admin",
    },
)

# Backend team has read access
bsr_team_config(
    name = "backend_team_config", 
    repositories = {
        "buf.build/company/schemas": "read",
    },
)
```

## Workflow Integration

### Team-Aware Builds

Buck2 builds automatically validate team permissions:

```python
enhanced_proto_library(
    name = "service_proto",
    srcs = ["service.proto"],
    bsr_deps = ["@company_schemas//platform:types"],
    team = "backend-team",  # Build validates team has access
    team_config = ":backend_team_config",
)
```

### Cross-Team Dependencies

The system supports and tracks cross-team dependencies:

```python
# Platform team service
enhanced_proto_library(
    name = "platform_service_proto",
    team = "platform-team",
    visibility = ["//backend-team:__pkg__"],  # Allow backend team access
)

# Backend team service using platform types
enhanced_proto_library(
    name = "backend_service_proto",
    deps = ["//platform-team:platform_service_proto"],
    team = "backend-team",
)
```

### Permission Change Propagation

Changes to team permissions are automatically propagated:

```python
# Update team permissions
changes = {
    "members": {
        "alice": {"role": "admin"}
    },
    "repositories": {
        "buf.build/company/schemas": {"access_level": "write"}
    }
}

result = team_manager.propagate_permission_changes(
    team="backend-team",
    changes=changes
)
```

## Configuration and Setup

### 1. Initialize Team Management

```bash
# Create a team
python -m tools.bsr_teams create \
    --name "platform-team" \
    --description "Platform infrastructure team"

# Add team members
python -m tools.bsr_teams add-member \
    --team "platform-team" \
    --username "alice" \
    --role "admin" \
    --email "alice@company.com"

# Configure repository access
python -m tools.bsr_teams add-repo \
    --team "platform-team" \
    --repository "buf.build/company/platform-schemas" \
    --access "admin"
```

### 2. Buck2 Configuration

Add team configuration to your `BUCK` file:

```python
load("//rules:bsr.bzl", "bsr_team_config", "enhanced_proto_library")

bsr_team_config(
    name = "team_config",
    team = "your-team",
    members = {
        "alice": "admin",
        "bob": "contributor",
    },
    repositories = {
        "buf.build/your-org/schemas": "write",
    },
)
```

### 3. Authentication Setup

Configure BSR authentication for team access:

```bash
# Set up service account for CI/CD
export BSR_SERVICE_ACCOUNT_KEY="path/to/service_account.json"

# Or use environment token
export BSR_TOKEN="your_bsr_token"
```

## Best Practices

### Team Organization

1. **Hierarchical Structure**: Organize teams hierarchically (engineering > platform-team > core-platform-team)
2. **Clear Responsibilities**: Each team should have clear ownership of specific repositories
3. **Minimal Permissions**: Grant minimum required access levels
4. **Regular Reviews**: Periodically review team memberships and permissions

### Repository Management

1. **Team-Specific Repositories**: Create repositories that align with team boundaries
2. **Shared Dependencies**: Use read-only access for shared/platform repositories
3. **Versioning Strategy**: Coordinate schema versioning across teams
4. **Documentation**: Document team responsibilities and repository purposes

### Access Control

1. **Role-Based Access**: Use roles rather than individual permissions where possible
2. **Temporary Access**: Use time-limited access for temporary team members
3. **Audit Trails**: Regularly review audit logs for permission changes
4. **Emergency Access**: Have procedures for emergency access grants

## Monitoring and Auditing

### Team Activity Monitoring

```python
# Get team information
team_info = team_manager.get_team_info("platform-team")
print(f"Team has {team_info['member_count']} members")
print(f"Access to {team_info['repository_count']} repositories")

# Get user's teams
user_teams = team_manager.get_user_teams("alice")
print(f"Alice is member of: {user_teams}")

# Get repository teams
repo_teams = team_manager.get_repository_teams("buf.build/company/schemas")
print(f"Repository accessible by teams: {repo_teams}")
```

### Permission Validation

```python
# Validate team permissions
is_valid = team_manager.validate_team_permissions(
    team="backend-team",
    repository="buf.build/company/schemas",
    username="alice",
    action="write"
)
```

### Audit Logging

All team management operations are automatically logged with:

- User who performed the action
- Team context
- Timestamp and action details
- Before/after state for changes

## Integration with Other Systems

### ORAS Registry Integration

Team configurations are automatically synchronized with ORAS for caching:

```python
# Team cache automatically uses team settings
from tools.bsr_team_oras_cache import BSRTeamOrasCache

team_cache = BSRTeamOrasCache(
    team="platform-team",
    bsr_client=bsr_client,
    oras_client=oras_client
)

# Enable shared caching for team
team_cache.enable_shared_cache(team_members)
```

### Authentication Integration

Seamless integration with existing BSR authentication:

```python
from tools.bsr_auth import BSRAuthenticator

# Team manager uses existing authentication
authenticator = BSRAuthenticator()
team_manager = BSRTeamManager(bsr_authenticator=authenticator)
```

## Troubleshooting

### Common Issues

1. **Permission Denied**: Check team membership and repository access levels
2. **Build Failures**: Verify team configuration targets exist and are correct
3. **Cache Issues**: Ensure team caching is properly configured
4. **Authentication Errors**: Verify BSR credentials and team access

### Debug Commands

```bash
# Check team information
python -m tools.bsr_teams info --team "platform-team"

# Validate permissions
python -m tools.bsr_teams validate \
    --team "platform-team" \
    --repository "buf.build/company/schemas" \
    --username "alice" \
    --action "write"

# List all teams
python -m tools.bsr_teams list
```

## Examples

See the complete team management example in [`examples/team-management/`](../examples/team-management/) which demonstrates:

- Multi-team organization structure
- Private repository access configuration
- Cross-team dependencies and collaboration
- Team-specific proto libraries with permission validation

## API Reference

### BSRTeamManager

The main interface for team management operations.

#### Methods

- `create_team(name, description, parent_team=None)`: Create a new team
- `delete_team(name, force=False)`: Delete a team
- `configure_team_access(team, repositories, access_level)`: Configure repository access
- `manage_team_members(team, members, action)`: Manage team membership
- `validate_team_permissions(team, repository, username, action)`: Validate permissions
- `propagate_permission_changes(team, changes)`: Propagate permission changes
- `get_team_info(team)`: Get comprehensive team information

### Buck2 Rules

#### `bsr_team_config`

Configure team settings for Buck2 builds.

**Attributes:**
- `team`: Team name
- `members`: Dictionary of team members and roles
- `repositories`: Dictionary of repository access configurations
- `settings`: Team-specific settings

#### `enhanced_proto_library`

Enhanced proto_library with team support.

**Additional Attributes:**
- `team`: Team name for team-aware builds
- `team_config`: Team configuration target

### Data Classes

#### `Team`
- `name`: Team name
- `description`: Team description
- `members`: Dictionary of team members
- `repositories`: Dictionary of repository access
- `parent_team`: Parent team name (optional)
- `child_teams`: Set of child team names

#### `TeamMember`
- `username`: Member username
- `role`: Member role (viewer, contributor, maintainer, admin)
- `email`: Member email (optional)
- `permissions`: Repository-specific permissions

#### `TeamRepository`
- `repository`: Repository reference
- `access_level`: Team's access level (read, write, admin)
- `team_permissions`: Member-specific permission overrides
