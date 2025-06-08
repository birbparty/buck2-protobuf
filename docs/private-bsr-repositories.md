# Private BSR Repository Support

This document describes how to configure and use private BSR (Buf Schema Registry) repositories with authentication and team-based access control.

## Overview

Private BSR repositories enable secure schema sharing within organizations through:

- **Authentication Integration**: Multiple authentication methods including service accounts, environment variables, and keychain storage
- **Team-Based Access Control**: Fine-grained permissions with read, write, and admin access levels
- **Seamless Integration**: Works alongside public BSR dependencies in the same project
- **Enterprise Security**: Secure credential management and access validation

## Quick Start

### 1. Configure Private Repository

```python
# In your BUCK file
load("//rules:bsr.bzl", "bsr_repository")

bsr_repository(
    name = "myorg_private_schemas",
    repository = "buf.build/myorg/private-schemas",
    auth_method = "service_account",
    teams = [
        "@platform-team:admin",
        "@backend-team:read",
        "@frontend-team:read"
    ],
    service_account_file = "//config:bsr_service_account.json",
    visibility = ["//..."],
)
```

### 2. Use in Proto Library

```python
load("//rules:bsr.bzl", "enhanced_proto_library")

enhanced_proto_library(
    name = "user_service_proto",
    srcs = ["user_service.proto"],
    bsr_deps = [
        # Private repository dependency
        "@myorg_private_schemas//common:types",
        
        # Public repository dependency
        "buf.build/googleapis/googleapis",
    ],
    bsr_repositories = {
        "@myorg_private_schemas": ":myorg_private_schemas",
    },
)
```

### 3. Set Up Authentication

```bash
# Configure team membership
python3 tools/bsr_private_auth.py add-team-member alice platform-team
python3 tools/bsr_private_auth.py add-team-member bob backend-team

# Test access validation
python3 tools/bsr_private_auth.py validate-access \
    buf.build/myorg/private-schemas --user alice --access-level read
```

## Configuration Reference

### Repository Configuration

The `bsr_repository` rule configures access to a private BSR repository:

```python
bsr_repository(
    name = "repo_config_name",           # Configuration name for reference
    repository = "buf.build/org/repo",   # BSR repository reference
    auth_method = "auto",                # Authentication method
    teams = ["@team1:read"],             # Team access specifications
    access_level = "read",               # Default access level
    service_account_file = None,         # Service account key file path
    cache_ttl = 3600,                    # Cache time-to-live in seconds
    visibility = ["//..."],              # Buck2 visibility specification
)
```

#### Parameters

- **`name`**: Unique identifier for this repository configuration
- **`repository`**: Full BSR repository reference (e.g., `buf.build/myorg/schemas`)
- **`auth_method`**: Authentication method to use:
  - `"auto"`: Try all methods in order (default)
  - `"environment"`: Use `BUF_TOKEN` or `BSR_TOKEN` environment variables
  - `"service_account"`: Use service account key file
  - `"keychain"`: Use system keychain/credential store
  - `"netrc"`: Use `.netrc` file credentials
  - `"interactive"`: Prompt for token interactively
- **`teams`**: List of team access specifications (format: `"@team-name:access-level"`)
- **`access_level`**: Default access level (`"read"`, `"write"`, `"admin"`)
- **`service_account_file`**: Path to service account JSON key file (for CI/CD)
- **`cache_ttl`**: How long to cache resolved dependencies (seconds)

### Access Levels

| Level   | Permissions                                    |
|---------|-----------------------------------------------|
| `read`  | Can consume schemas from the repository       |
| `write` | Can consume and publish schemas               |
| `admin` | Full access including repository management   |

Access levels are hierarchical: `admin` includes `write` and `read` permissions, `write` includes `read` permissions.

### Team Specifications

Teams can be specified in multiple formats:

```python
teams = [
    "@platform-team",           # Default to read access
    "@backend-team:write",      # Explicit write access
    "@admin-team:admin",        # Admin access
]
```

## Authentication Methods

### Environment Variables

Set `BUF_TOKEN` or `BSR_TOKEN` environment variable:

```bash
export BUF_TOKEN="your-bsr-api-token"
```

### Service Account (Recommended for CI/CD)

1. Create service account key file:
```json
{
  "account_id": "your-service-account-id",
  "private_key": "your-private-key"
}
```

2. Configure repository to use service account:
```python
bsr_repository(
    name = "private_repo",
    repository = "buf.build/myorg/schemas",
    auth_method = "service_account",
    service_account_file = "//config:service_account.json",
)
```

### System Keychain

Store credentials in system keychain (macOS Keychain, Windows Credential Manager, Linux Secret Service):

```bash
# Store credentials (done once)
python3 tools/bsr_auth.py auth --repository buf.build/myorg/schemas

# Credentials are automatically retrieved from keychain
```

### .netrc File

Add BSR credentials to `~/.netrc`:

```
machine buf.build
login your-username
password your-api-token
```

## Team Management

### Configure Teams

```bash
# Add users to teams
python3 tools/bsr_private_auth.py add-team-member alice platform-team
python3 tools/bsr_private_auth.py add-team-member bob backend-team
python3 tools/bsr_private_auth.py add-team-member charlie frontend-team

# Remove users from teams
python3 tools/bsr_private_auth.py remove-team-member alice platform-team
```

### Validate Access

```bash
# Check if user has access to repository
python3 tools/bsr_private_auth.py validate-access \
    buf.build/myorg/private-schemas --user alice --access-level read

# List repositories accessible to user
python3 tools/bsr_private_auth.py list-accessible --user alice
```

### Repository Management

```bash
# List configured private repositories
python3 tools/bsr_private_auth.py list-repos

# Configure new private repository
python3 tools/bsr_private_auth.py configure buf.build/myorg/new-repo \
    --auth-method service_account \
    --teams platform-team:admin backend-team:read
```

## Advanced Usage

### Mixed Public and Private Dependencies

```python
enhanced_proto_library(
    name = "service_proto",
    srcs = ["service.proto"],
    bsr_deps = [
        # Private repositories
        "@myorg_platform//common:types",
        "@myorg_internal//auth:v1",
        
        # Public repositories  
        "buf.build/googleapis/googleapis",
        "buf.build/grpc-ecosystem/grpc-gateway:v2.0.0",
        "buf.build/envoyproxy/protoc-gen-validate:v0.10.1",
    ],
    bsr_repositories = {
        "@myorg_platform": ":platform_repo_config",
        "@myorg_internal": ":internal_repo_config",
    },
)
```

### Repository-Specific Authentication

```python
# Different authentication methods for different repositories
bsr_repository(
    name = "production_schemas",
    repository = "buf.build/myorg/production",
    auth_method = "service_account",
    service_account_file = "//config:prod_service_account.json",
    teams = ["@platform-team:admin"],
)

bsr_repository(
    name = "dev_schemas", 
    repository = "buf.build/myorg/development",
    auth_method = "environment",  # Use BUF_TOKEN env var
    teams = ["@platform-team:admin", "@backend-team:write"],
)
```

### CI/CD Integration

#### GitHub Actions

```yaml
name: Build with Private BSR

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up BSR Service Account
        run: |
          echo '${{ secrets.BSR_SERVICE_ACCOUNT_KEY }}' > service_account.json
          
      - name: Configure BSR Authentication
        run: |
          python3 tools/bsr_private_auth.py configure \
            buf.build/myorg/private-schemas \
            --auth-method service_account \
            --service-account-file ./service_account.json
            
      - name: Build Proto Libraries
        run: buck2 build //...
```

#### GitLab CI

```yaml
build:
  script:
    - echo "$BSR_SERVICE_ACCOUNT_KEY" > service_account.json
    - python3 tools/bsr_private_auth.py configure buf.build/myorg/schemas --auth-method service_account --service-account-file ./service_account.json
    - buck2 build //...
  variables:
    BSR_SERVICE_ACCOUNT_KEY: $BSR_SERVICE_ACCOUNT_KEY
```

## Error Handling

### Common Access Errors

**Access Denied**
```
ERROR: Access denied to private repository: buf.build/myorg/private-schemas
```
- Verify team membership: `python3 tools/bsr_private_auth.py list-accessible --user username`
- Check repository configuration: `python3 tools/bsr_private_auth.py list-repos`

**Authentication Failed**
```
ERROR: All authentication methods failed for buf.build/myorg/schemas
```
- Verify credentials are configured: `python3 tools/bsr_auth.py status --repository buf.build/myorg/schemas`
- Check service account file exists and is valid
- Ensure environment variables are set correctly

**Repository Not Found**
```
ERROR: No configuration found for private repository: @myorg_schemas
```
- Verify `bsr_repository` rule is defined with correct name
- Check `bsr_repositories` mapping in `enhanced_proto_library`

### Debugging

Enable verbose logging:

```bash
# Verbose authentication
python3 tools/bsr_private_auth.py --verbose auth buf.build/myorg/schemas

# Verbose dependency resolution
export BSR_VERBOSE=1
buck2 build //path/to:target
```

## Security Best Practices

### Credential Management

1. **Use Service Accounts for CI/CD**: Never commit API tokens to version control
2. **Rotate Credentials Regularly**: Update service account keys periodically
3. **Principle of Least Privilege**: Grant minimum required access levels
4. **Audit Access**: Regularly review team memberships and repository access

### Repository Configuration

1. **Separate Environments**: Use different repositories for dev/staging/production
2. **Team Isolation**: Configure teams based on organizational boundaries  
3. **Access Logging**: Monitor repository access patterns
4. **Backup Configurations**: Version control BSR repository configurations

### Network Security

1. **HTTPS Only**: BSR communication is encrypted over HTTPS
2. **Firewall Rules**: Restrict BSR access to authorized networks in enterprise environments
3. **VPN Access**: Require VPN for private repository access if needed

## Troubleshooting

### Performance Issues

**Slow Dependency Resolution**
- Increase cache TTL: `cache_ttl = 7200`
- Use ORAS registry caching: Configure `oras.birb.homes` 
- Check network connectivity to BSR

**Build Cache Misses**
- Verify consistent authentication across team members
- Use shared service accounts for consistent cache keys
- Configure remote caching with authenticated BSR access

### Team Management Issues

**User Cannot Access Repository**
1. Verify user is added to correct team:
   ```bash
   python3 tools/bsr_private_auth.py list-accessible --user username
   ```

2. Check team has repository access:
   ```bash
   python3 tools/bsr_private_auth.py list-repos
   ```

3. Validate access level requirements:
   ```bash
   python3 tools/bsr_private_auth.py validate-access repo --user username --access-level read
   ```

**Inconsistent Team State**
- Clear and reconfigure team memberships:
  ```bash
  # Clear cache and reconfigure
  rm -rf ~/.cache/buck2-protobuf/bsr-auth/
  python3 tools/bsr_private_auth.py configure ...
  ```

## Integration with Infrastructure Team

For infrastructure requirements or ORAS registry configuration, create a request:

```bash
# Create infrastructure request
cat > infrastructure_request.md << EOF
# BSR Private Repository Infrastructure Request

## Requirements
- Private BSR repository hosting for myorg
- ORAS registry cache configuration for oras.birb.homes
- Service account key management for CI/CD

## Justification
Secure schema sharing for enterprise protobuf development with team-based access control.

## Technical Details
- Expected repositories: buf.build/myorg/{platform,internal,public}
- Team structure: platform-team (admin), backend-team (write), frontend-team (read)
- CI/CD integration: GitHub Actions + GitLab CI

## Timeline
Needed for Q1 2025 enterprise deployment
EOF

# Infrastructure team will handle via AI agents in $HOME/git/birb-home
```

## Examples

See working examples in:
- `examples/private-bsr/` - Complete private BSR setup
- `examples/authentication/` - Authentication method examples
- `test/` - Comprehensive test suite

## API Reference

For detailed API documentation, see:
- `tools/bsr_private_auth.py` - Private BSR authentication CLI
- `rules/bsr.bzl` - Buck2 rules for BSR repositories
- `docs/bsr-authentication.md` - Base authentication system

## Migration Guide

### From Public to Private Repositories

1. **Configure Private Repository**:
   ```python
   bsr_repository(
       name = "myorg_schemas",
       repository = "buf.build/myorg/schemas",  # Now private
       auth_method = "service_account",
       teams = ["@platform-team:admin"],
   )
   ```

2. **Update Dependencies**:
   ```python
   # Before (public)
   bsr_deps = ["buf.build/myorg/schemas"]
   
   # After (private)
   bsr_deps = ["@myorg_schemas//module:version"]
   bsr_repositories = {"@myorg_schemas": ":myorg_schemas"}
   ```

3. **Set Up Team Access**:
   ```bash
   python3 tools/bsr_private_auth.py add-team-member alice platform-team
   python3 tools/bsr_private_auth.py add-team-member bob backend-team
   ```

4. **Configure CI/CD**:
   - Add service account secrets
   - Update build scripts to configure authentication
   - Test access validation

### Migration Checklist

- [ ] Repository configured with correct teams
- [ ] Team memberships established
- [ ] Authentication working in development
- [ ] CI/CD authentication configured
- [ ] Access validation tested
- [ ] Documentation updated
- [ ] Team training completed

This completes the private BSR repository support, enabling secure enterprise protobuf development with comprehensive team-based access control.
