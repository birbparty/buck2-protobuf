# BSR Publishing Examples

This directory demonstrates automated BSR publishing workflows with semantic versioning, multi-registry support, and team governance.

## Overview

The BSR publishing system provides professional schema release management with:

- **Semantic Versioning**: Automatic version detection based on schema changes
- **Multi-Registry Publishing**: Atomic publishing to BSR + ORAS registries  
- **Team Governance**: Approval workflows and notifications
- **CI/CD Integration**: Automated publishing pipelines

## Example APIs

### User API (`user_api.proto`)
Core user management service demonstrating:
- CRUD operations for user entities
- Standard REST-like gRPC patterns
- Proper proto3 syntax and conventions

### Payment API (`payment_api.proto`)
Payment processing service showing:
- Dependency on User API
- Complex business logic modeling
- Money handling patterns

### Notification API (`notification_api.proto`)
Notification system demonstrating:
- Multi-channel notification support
- User preferences management
- Priority and status tracking

## Publishing Examples

### 1. Simple Single-Registry Publishing

```bash
# Publish user API to BSR only
buck2 run //examples/bsr-publishing:publish_user_api
```

This example shows basic publishing to a single BSR registry with team notifications.

### 2. Multi-Registry with Governance

```bash
# Publish payment API with governance
buck2 run //examples/bsr-publishing:publish_payment_api
```

Features:
- Publishing to both BSR and ORAS registries atomically
- Breaking change approval requirements
- Team review workflow
- Multi-team notifications

### 3. Batch Publishing

```bash
# Publish all APIs together
buck2 run //examples/bsr-publishing:publish_all_apis
```

Demonstrates:
- Parallel publishing of multiple schemas
- Coordinated versioning across services
- Batch success/failure handling

### 4. Environment-Specific Publishing

```bash
# Development publishing (lenient)
buck2 run //examples/bsr-publishing:publish_dev_apis

# Production publishing (strict)
buck2 run //examples/bsr-publishing:publish_prod_apis
```

Shows different governance policies:
- **Development**: Allow breaking changes, minimal review
- **Production**: Block breaking changes, require approval

## Version Management

The publishing system uses intelligent semantic versioning:

### Version Detection
- **MAJOR**: Breaking changes (field removal, type changes)
- **MINOR**: New features (new fields, services, methods)
- **PATCH**: Bug fixes, documentation updates

### Change Analysis
The version manager analyzes:
- Proto file additions/removals
- Field and service changes
- Breaking change detection via `buf breaking`
- Git commit information

Example version progression:
```
v1.0.0 -> v1.1.0  (added new field)
v1.1.0 -> v1.1.1  (documentation update)
v1.1.1 -> v2.0.0  (removed field - breaking)
```

## Multi-Registry Publishing

### Registry Configuration

```python
bsr_publish(
    name = "publish_with_backup",
    proto = ":api_proto",
    repositories = {
        "primary": "buf.build/myorg/api",
        "backup": "oras.birb.homes/myorg/api",
        "mirror": "registry.company.com/myorg/api"
    }
)
```

### Atomic Publishing
- All registries must succeed or all rollback
- Version consistency checking across registries
- Registry health validation before publishing
- Automatic fallback and recovery

## Team Governance

### Breaking Change Policies

#### Allow (Development)
```python
breaking_change_policy = "allow"
```
- Breaking changes publish immediately
- Suitable for development environments

#### Require Approval (Staging)
```python
breaking_change_policy = "require_approval"
notify_teams = ["@platform-team", "@api-consumers"]
```
- Breaking changes require team approval
- Notifications sent to affected teams
- Manual intervention required

#### Block (Production)
```python
breaking_change_policy = "block"
```
- Breaking changes are rejected
- Suitable for production environments
- Forces non-breaking evolution

### Team Notifications

Teams receive email notifications for:
- Successful publications
- Failed publications
- Breaking change approvals needed
- Version releases

## CI/CD Integration

### GitHub Actions

```yaml
name: Publish Schemas
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Buck2
        run: # ... setup steps
      - name: Publish to BSR
        run: buck2 run //schemas:publish_all_apis
        env:
          BUF_TOKEN: ${{ secrets.BUF_TOKEN }}
```

### GitLab CI

```yaml
publish-schemas:
  stage: deploy
  only:
    - tags
  script:
    - buck2 run //schemas:publish_all_apis
  variables:
    BUF_TOKEN: $BUF_TOKEN
```

## Testing Against oras.birb.homes

This project includes integration with `oras.birb.homes` for testing:

```bash
# Test publishing to ORAS registry
buck2 run //examples/bsr-publishing:publish_notification_api
```

The system automatically:
- Detects ORAS registry URLs
- Uses appropriate ORAS client
- Handles authentication
- Provides fallback if BSR is unavailable

## Best Practices

### Schema Evolution
1. Always add new fields as optional
2. Never remove or change existing field numbers
3. Use deprecation markers before removal
4. Version your packages (v1, v2, etc.)

### Publishing Workflow
1. Develop schemas in feature branches
2. Use development publishing for testing
3. Require approval for breaking changes
4. Automate production publishing via CI/CD
5. Monitor team notifications

### Version Management
1. Let the system detect version increments
2. Use git tags for manual versioning when needed
3. Include meaningful commit messages
4. Document breaking changes in release notes

## Common Commands

```bash
# Check what would be published
buck2 run //tools:bsr_version_manager -- \
  --repository "buf.build/myorg/api" \
  --proto-files examples/bsr-publishing/user_api.proto \
  --verbose

# Test publishing workflow
buck2 test //tools:test_bsr_publisher

# Validate all examples
buck2 test //test:validate_buf_integration_examples
```

## Troubleshooting

### Publishing Failures
1. Check BSR authentication: `buck2 run //tools:bsr_auth -- status`
2. Verify team permissions
3. Review breaking change policy
4. Check registry connectivity

### Version Issues
1. Ensure git repository is clean
2. Check for semantic versioning conflicts
3. Verify baseline version availability
4. Review change detection logs

### Team Notifications
1. Verify team configurations
2. Check email addresses in team data
3. Review notification permissions
4. Test SMTP configuration

## Additional Resources

- [BSR Documentation](https://buf.build/docs/bsr)
- [Buck2 Rules Reference](../../docs/rules-reference.md)
- [Team Management Guide](../../docs/bsr-team-management.md)
- [Authentication Setup](../../docs/bsr-authentication.md)
