# 🔍 Basic Linting Example

This example demonstrates the fundamentals of buf linting with buck2-protobuf. It shows how to set up basic linting rules and understand common validation patterns.

## What You'll Learn

- Setting up basic buf_lint rules
- Understanding default lint rules
- Customizing lint configuration
- Interpreting and fixing lint errors
- Best practices for API design

## Files Overview

- `user_service.proto` - Well-formatted service following buf best practices
- `bad_example.proto` - Example with common linting issues to demonstrate violations
- `buf.yaml` - Configuration file with basic lint rules
- `BUCK` - Build definitions showing different linting approaches

## Example Structure

```
basic-lint/
├── BUCK                    # Build definitions
├── README.md              # This documentation
├── buf.yaml               # Buf configuration
├── user_service.proto     # Good example
└── bad_example.proto      # Example with issues
```

## Core Concepts

### 🎯 Default Lint Rules

Buf provides sensible defaults that enforce:

- **Naming Conventions**: PascalCase for messages/services, snake_case for fields
- **Comments**: All public elements must be documented
- **Package Structure**: Proper package organization
- **Field Numbering**: Consistent field number assignment

### 📋 Common Lint Rules

| Rule | Purpose | Example |
|------|---------|---------|
| `MESSAGE_NAMES_PASCAL_CASE` | Messages use PascalCase | `UserProfile` ✅ vs `user_profile` ❌ |
| `FIELD_NAMES_LOWER_SNAKE_CASE` | Fields use snake_case | `user_id` ✅ vs `UserID` ❌ |
| `SERVICE_NAMES_PASCAL_CASE` | Services use PascalCase | `UserService` ✅ vs `userService` ❌ |
| `ENUM_ZERO_VALUE_SUFFIX` | First enum value ends with `_UNSPECIFIED` | `STATUS_UNSPECIFIED = 0` ✅ |
| `COMMENTS` | All public elements documented | Every message/field has comments ✅ |

### ⚙️ Configuration Options

The `buf.yaml` file controls linting behavior:

```yaml
lint:
  use:
    - DEFAULT                    # Enable default rule set
    - COMMENTS                   # Require documentation
    - FIELD_NAMES_LOWER_SNAKE_CASE  # Enforce field naming
  except:
    - PACKAGE_VERSION_SUFFIX    # Disable version suffix requirement
  enum_zero_value_suffix: _UNSPECIFIED
  service_suffix: Service
```

## Running the Examples

### 1. Basic Linting (Should Pass)
```bash
# Lint with automatic config discovery
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_basic

# Lint with explicit config
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_explicit_config

# Lint with rule overrides
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_with_overrides
```

### 2. Strict Linting (Production Rules)
```bash
# Apply strict production rules
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_strict
```

### 3. Minimal Linting (Permissive)
```bash
# Apply minimal rules for legacy compatibility
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_minimal
```

### 4. Demonstrating Violations (Will Fail)
```bash
# See what linting violations look like
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_bad_example
```

### 5. Format Checking
```bash
# Check format without changing files
buck2 run //examples/buf-integration/quickstart/basic-lint:format_check

# Auto-format files
buck2 run //examples/buf-integration/quickstart/basic-lint:format_write
```

## Understanding Lint Output

### ✅ Successful Lint Output
```
$ buck2 run //examples/buf-integration/quickstart/basic-lint:lint_basic
BUILD SUCCEEDED
```

### ❌ Failed Lint Output Example
```
$ buck2 run //examples/buf-integration/quickstart/basic-lint:lint_bad_example
bad_example.proto:8:1:SERVICE_NAMES_PASCAL_CASE:Service name "badService" should be PascalCase and end with "Service"
bad_example.proto:10:3:RPC_NAMES_PASCAL_CASE:RPC name "getuser" should be PascalCase
bad_example.proto:17:1:MESSAGE_NAMES_PASCAL_CASE:Message name "getUserReq" should be PascalCase
bad_example.proto:18:3:FIELD_NAMES_LOWER_SNAKE_CASE:Field name "UserID" should be lower_snake_case
BUILD FAILED
```

## Common Violations and Fixes

### 1. Naming Convention Issues

**❌ Wrong:**
```protobuf
service userService {  // Should be PascalCase
  rpc getUser(getUserReq) returns (getUserResp);  // Should be PascalCase
}

message getUserReq {  // Should be PascalCase
  string UserID = 1;  // Should be snake_case
}
```

**✅ Correct:**
```protobuf
service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}

message GetUserRequest {
  string user_id = 1;
}
```

### 2. Missing Comments

**❌ Wrong:**
```protobuf
service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}
```

**✅ Correct:**
```protobuf
// UserService provides user management operations.
service UserService {
  // GetUser retrieves a user by their unique identifier.
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}
```

### 3. Enum Zero Value

**❌ Wrong:**
```protobuf
enum Status {
  ACTIVE = 0;    // Should be UNSPECIFIED
  INACTIVE = 1;
}
```

**✅ Correct:**
```protobuf
enum Status {
  STATUS_UNSPECIFIED = 0;  // Required first value
  STATUS_ACTIVE = 1;
  STATUS_INACTIVE = 2;
}
```

## Configuration Patterns

### Development Configuration (Permissive)
```yaml
lint:
  use:
    - DEFAULT
  except:
    - COMMENTS
    - PACKAGE_VERSION_SUFFIX
    - FIELD_NAMES_LOWER_SNAKE_CASE
```

### Production Configuration (Strict)
```yaml
lint:
  use:
    - DEFAULT
    - COMMENTS
    - FIELD_NAMES_LOWER_SNAKE_CASE
    - SERVICE_NAMES_PASCAL_CASE
    - ENUM_NAMES_UPPER_SNAKE_CASE
    - MESSAGE_NAMES_PASCAL_CASE
    - RPC_NAMES_PASCAL_CASE
  enum_zero_value_suffix: _UNSPECIFIED
  service_suffix: Service
```

### Team-Specific Configuration
```yaml
lint:
  use:
    - DEFAULT
    - COMMENTS
  except:
    - PACKAGE_VERSION_SUFFIX
  enum_zero_value_suffix: _UNKNOWN  # Team preference
  service_suffix: API               # Team convention
```

## Best Practices

### 1. Start with Default Rules
Begin with buf's default rule set and customize as needed:
```yaml
lint:
  use:
    - DEFAULT
```

### 2. Document Everything
Always include comments for public APIs:
```protobuf
// UserService provides comprehensive user management.
service UserService {
  // CreateUser creates a new user account.
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
}
```

### 3. Use Consistent Naming
Follow buf's naming conventions consistently:
- **Services**: `PascalCase` ending with `Service`
- **Messages**: `PascalCase`
- **Fields**: `snake_case`
- **Enums**: `UPPER_SNAKE_CASE`

### 4. Handle Enum Defaults
Always start enums with `_UNSPECIFIED`:
```protobuf
enum UserStatus {
  USER_STATUS_UNSPECIFIED = 0;
  USER_STATUS_ACTIVE = 1;
  USER_STATUS_INACTIVE = 2;
}
```

### 5. Use Meaningful Packages
Organize code with descriptive package names:
```protobuf
package examples.quickstart.user.v1;
```

## Troubleshooting

### Common Issues

**"Package not found" Error:**
- Ensure `buf.yaml` is in the correct location
- Check package name matches directory structure

**"Multiple lint errors" Output:**
- Fix violations one by one
- Use `--verbose` flag for detailed output

**"Configuration not found" Error:**
- Verify `buf.yaml` syntax is correct
- Check file permissions

### Getting Help

- Check the [buf documentation](https://buf.build/docs) for rule details
- Use `buf lint --help` for command options
- Review the `bad_example.proto` to see common violations

## Next Steps

After mastering basic linting:

1. **[Formatting Example](../formatting/)** - Learn automated code formatting
2. **[Breaking Changes](../breaking/)** - Understand compatibility checking
3. **[Configuration Discovery](../config-discovery/)** - Advanced configuration patterns
4. **[BSR Dependencies](../bsr-deps/)** - External dependency management

---

**Master these linting fundamentals to build high-quality, consistent protobuf APIs! 🚀**
