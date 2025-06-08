# BSR Authentication System

The BSR Authentication System provides comprehensive multi-method authentication for accessing the Buf Schema Registry (BSR), including support for private repositories and team collaboration workflows.

## Overview

The authentication system supports multiple authentication methods with automatic fallback and secure credential storage:

- **Environment Variables** - `BUF_TOKEN`, `BSR_TOKEN`
- **System Keychain** - Secure OS-level credential storage
- **.netrc Files** - Standard Unix authentication files
- **Service Accounts** - CI/CD automation with key files
- **Interactive Authentication** - Manual token entry

## Quick Start

### Basic Authentication

```python
from tools.bsr_auth import BSRAuthenticator

# Initialize authenticator
authenticator = BSRAuthenticator(verbose=True)

# Authenticate (auto-detects method)
credentials = authenticator.authenticate()
print(f"Authenticated using: {credentials.auth_method}")
```

### Authentication with Specific Method

```python
# Environment variable authentication
credentials = authenticator.authenticate(method="environment")

# Interactive authentication
credentials = authenticator.authenticate(method="interactive")

# Service account authentication
credentials = authenticator.authenticate(
    method="service_account",
    service_account_file="./service_account.json"
)
```

## Authentication Methods

### 1. Environment Variables

The simplest method for CI/CD and development:

```bash
export BUF_TOKEN="your_bsr_token_here"
# or
export BSR_TOKEN="your_bsr_token_here"
```

```python
# Automatically detected
credentials = authenticator.authenticate()
```

### 2. System Keychain

Secure storage for developer workstations:

```python
# Store credentials securely
authenticator.authenticate(method="interactive")  # Prompts and stores

# Later retrieval (automatic)
credentials = authenticator.authenticate()  # Uses stored credentials
```

### 3. .netrc Files

Standard Unix authentication format in `~/.netrc`:

```
machine buf.build
login your_username
password your_bsr_token

machine private-bsr.company.com
login your_username
password your_private_token
```

### 4. Service Accounts

For CI/CD automation with JSON key files:

```json
{
  "account_id": "ci-service-account",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----",
  "registry": "buf.build"
}
```

```python
credentials = authenticator.authenticate(
    method="service_account",
    service_account_file="./ci_service_account.json"
)
```

### 5. Interactive Authentication

Manual token entry for initial setup:

```python
# Prompts user for token
credentials = authenticator.authenticate(method="interactive")
```

## BSR Client Integration

The BSR client automatically handles authentication:

```python
from tools.bsr_client import BSRClient

# Auto-authentication enabled by default
client = BSRClient(verbose=True)

# Download private dependencies
dependencies = client.resolve_dependencies(Path("buf.yaml"))
```

### Manual Authentication Control

```python
# Disable auto-authentication
client = BSRClient(auto_authenticate=False)

# Explicit authentication
credentials = client.authenticate(method="environment")

# Check authentication status
status = client.get_authentication_status()
print(f"Authenticated: {status['authenticated']}")
```

## Command Line Interface

### Authenticate

```bash
# Auto-detect authentication method
python tools/bsr_auth.py auth

# Use specific method
python tools/bsr_auth.py auth --method environment
python tools/bsr_auth.py auth --method interactive

# Service account authentication
python tools/bsr_auth.py auth --method service_account --service-account-file ./sa.json
```

### Check Status

```bash
# Check authentication status
python tools/bsr_auth.py status

# Check specific repository
python tools/bsr_auth.py status --repository buf.build/myorg
```

### List Authenticated Repositories

```bash
python tools/bsr_auth.py list
```

### Logout

```bash
# Logout from all repositories
python tools/bsr_auth.py logout

# Logout from specific repository
python tools/bsr_auth.py logout --repository buf.build/myorg
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Build with Private BSR Dependencies
on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up authentication
        env:
          BUF_TOKEN: ${{ secrets.BUF_TOKEN }}
        run: |
          python tools/bsr_auth.py auth --method environment
          python tools/bsr_auth.py status
      
      - name: Build with private dependencies
        run: |
          buck2 build //...
```

### Service Account Pattern

```yaml
- name: Authenticate with service account
  env:
    BSR_SERVICE_ACCOUNT_KEY: ${{ secrets.BSR_SERVICE_ACCOUNT_KEY }}
  run: |
    echo "$BSR_SERVICE_ACCOUNT_KEY" > /tmp/sa.json
    python tools/bsr_auth.py auth --method service_account --service-account-file /tmp/sa.json
```

## Security Features

### Secure Credential Storage

- **System Keyring**: Uses OS-level secure storage (Keychain on macOS, Windows Credential Store, etc.)
- **Encrypted Files**: Fallback with AES encryption when keyring unavailable
- **Restricted Permissions**: Files created with 600 permissions (owner read/write only)

### Token Validation

```python
# Validate token format
credentials = BSRCredentials(token="your_token")  # Validates format

# Test repository access
is_valid = authenticator.validate_access("buf.build/myorg", credentials)
```

### Audit Logging

Authentication attempts are logged for security auditing:

```python
authenticator = BSRAuthenticator(verbose=True)  # Enable detailed logging
```

## Team Collaboration

### Shared Team Configuration

```python
# Team-specific BSR client
client = BSRClient(
    team="platform-team",
    registry_url="buf.build",
    verbose=True
)

# Access team dependencies
team_deps = client.get_team_dependencies()
```

### Multiple Registry Support

```python
# Authenticate for multiple registries
authenticator.authenticate(repository="buf.build")
authenticator.authenticate(repository="private-bsr.company.com")

# List all authenticated repositories
repos = authenticator.list_authenticated_repositories()
```

## Error Handling

### Common Authentication Errors

```python
from tools.bsr_auth import BSRAuthenticationError

try:
    credentials = authenticator.authenticate()
except BSRAuthenticationError as e:
    print(f"Authentication failed: {e}")
    # Handle authentication failure
```

### Credential Validation

```python
# Check if credentials are expired
if credentials.is_expired():
    # Re-authenticate
    credentials = authenticator.authenticate()
```

## Advanced Configuration

### Custom Cache Directory

```python
authenticator = BSRAuthenticator(
    cache_dir=Path("/custom/cache/path"),
    verbose=True
)
```

### Authentication Priority

The auto-detection follows this priority order:

1. **Environment Variables** (`BUF_TOKEN`, `BSR_TOKEN`)
2. **Service Account Keys** (CI/CD environments)
3. **System Keychain** (Developer workstations)
4. **Netrc Files** (`~/.netrc`)
5. **Interactive Prompt** (Last resort)

### Credential Expiration

```python
# Set token expiration (1 hour from now)
credentials = BSRCredentials(
    token="your_token",
    expires_at=time.time() + 3600
)
```

## Troubleshooting

### Debug Authentication Issues

```bash
# Enable verbose logging
python tools/bsr_auth.py --verbose auth

# Check authentication status
python tools/bsr_auth.py --verbose status
```

### Clear Stored Credentials

```bash
# Clear all stored credentials
python tools/bsr_auth.py logout

# Clear credentials for specific repository
python tools/bsr_auth.py logout --repository buf.build/myorg
```

### Validate Buf CLI Installation

```python
from tools.bsr_client import BSRClient

try:
    client = BSRClient()
    print("✅ Buf CLI is working correctly")
except Exception as e:
    print(f"❌ Buf CLI issue: {e}")
```

## API Reference

### BSRAuthenticator

```python
class BSRAuthenticator:
    def __init__(self, cache_dir=None, registry="buf.build", verbose=False):
        """Initialize BSR authenticator."""
    
    def authenticate(self, repository=None, method="auto", **kwargs) -> BSRCredentials:
        """Authenticate with BSR using specified method."""
    
    def validate_access(self, repository: str, credentials: BSRCredentials) -> bool:
        """Validate BSR repository access with credentials."""
    
    def logout(self, repository=None) -> bool:
        """Logout and clear stored credentials."""
    
    def get_authentication_status(self, repository=None) -> Dict:
        """Get authentication status for a repository."""
```

### BSRCredentials

```python
@dataclass
class BSRCredentials:
    token: str
    username: Optional[str] = None
    registry: str = "buf.build"
    expires_at: Optional[float] = None
    auth_method: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if credentials are expired."""
    
    def mask_token(self) -> str:
        """Return masked token for safe logging."""
```

## Examples

See the `examples/` directory for complete examples:

- `examples/authentication/basic_auth.py`
- `examples/authentication/ci_cd_pattern.py`
- `examples/authentication/team_collaboration.py`

## Security Considerations

1. **Never commit tokens to version control**
2. **Use service accounts for CI/CD automation**
3. **Regularly rotate authentication tokens**
4. **Monitor authentication logs for suspicious activity**
5. **Use encrypted storage for team shared credentials**

## Next Steps

After setting up authentication, you can:

1. **Access Private Repositories** - Use private BSR dependencies in your builds
2. **Team Management** - Set up team access controls and shared credentials
3. **Publishing Workflows** - Publish your own modules to private BSR repositories
4. **Breaking Change Detection** - Enable advanced BSR governance features

For more information, see:
- [Private BSR Repositories](private-bsr-repositories.md)
- [BSR Team Management](bsr-team-management.md)
- [BSR Publishing Workflows](bsr-publishing-workflows.md)
