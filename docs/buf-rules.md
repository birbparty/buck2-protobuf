# Buf Rules Documentation

This document provides comprehensive documentation for the buf rules in the buck2-protobuf integration. These rules bring modern protobuf development workflows directly into Buck2 with proper caching, error handling, and seamless integration.

## Overview

The buf rules provide three core operations for protobuf development:

- **`buf_lint`** - Validates protobuf files using buf's comprehensive linting rules
- **`buf_format`** - Formats protobuf files according to buf's style guide
- **`buf_breaking`** - Detects breaking changes in protobuf files

All rules integrate with Buck2's caching system to prevent redundant operations and provide clear, actionable error messages.

## Prerequisites

The buf rules require:
- Buck2 build system
- Buf CLI (automatically distributed via ORAS)
- Python 3.6+ (for toolchain scripts)

## Quick Start

### Basic Linting

```starlark
load("//rules:buf.bzl", "buf_lint")

buf_lint(
    name = "lint_api",
    srcs = ["api.proto", "types.proto"],
    visibility = ["PUBLIC"],
)
```

### Format Checking

```starlark
load("//rules:buf.bzl", "buf_format")

buf_format(
    name = "format_check",
    srcs = ["api.proto"],
    diff = True,  # Show differences without modifying files
    visibility = ["PUBLIC"],
)
```

### Breaking Change Detection

```starlark
load("//rules:buf.bzl", "buf_breaking")

buf_breaking(
    name = "check_breaking",
    srcs = ["api.proto"],
    against = "//baseline:api_proto",
    visibility = ["PUBLIC"],
)
```

## Rule Reference

### buf_lint

Validates protobuf files using buf's comprehensive linting rules.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `string` | required | Unique name for this lint target |
| `srcs` | `list[source]` | required | List of .proto files to lint |
| `buf_yaml` | `source` | `None` | Optional buf.yaml configuration file |
| `config` | `dict[string, string]` | `{}` | Inline lint configuration options |
| `fail_on_error` | `bool` | `True` | Whether to fail the build on lint violations |
| `visibility` | `list[string]` | `["//visibility:private"]` | Buck2 visibility specification |

#### Configuration Options

The `config` attribute supports the following lint configuration options:

```starlark
buf_lint(
    name = "lint_strict",
    srcs = ["api.proto"],
    config = {
        "use": ["DEFAULT", "COMMENTS", "FIELD_NAMES_LOWER_SNAKE_CASE"],
        "except": ["PACKAGE_VERSION_SUFFIX"],
        "enum_zero_value_suffix": "_UNSPECIFIED",
        "rpc_allow_same_request_response": "false",
        "rpc_allow_google_protobuf_empty_requests": "true",
        "rpc_allow_google_protobuf_empty_responses": "true",
        "service_suffix": "Service",
    },
)
```

#### Output Files

- `buf_lint_report.json` - Machine-readable lint report
- `buf_lint_report.txt` - Human-readable lint report

#### Examples

**Basic linting with default rules:**

```starlark
buf_lint(
    name = "lint_user_proto",
    srcs = [
        "user.proto",
        "user_types.proto",
    ],
)
```

**Linting with custom configuration:**

```starlark
buf_lint(
    name = "lint_strict",
    srcs = ["api.proto"],
    config = {
        "use": ["DEFAULT", "COMMENTS"],
        "except": ["PACKAGE_VERSION_SUFFIX"],
        "enum_zero_value_suffix": "_UNSPECIFIED",
    },
)
```

**Linting with buf.yaml configuration file:**

```starlark
buf_lint(
    name = "lint_with_config",
    srcs = ["api.proto"],
    buf_yaml = "buf.yaml",
)
```

### buf_format

Formats protobuf files according to buf's style guide.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `string` | required | Unique name for this format target |
| `srcs` | `list[source]` | required | List of .proto files to format |
| `diff` | `bool` | `False` | Show formatting differences without changing files |
| `write` | `bool` | `False` | Generate formatted files as outputs |
| `buf_yaml` | `source` | `None` | Optional buf.yaml configuration file |
| `visibility` | `list[string]` | `["//visibility:private"]` | Buck2 visibility specification |

#### Modes

**Diff mode** (recommended for CI validation):
```starlark
buf_format(
    name = "format_check",
    srcs = ["api.proto"],
    diff = True,
)
```

**Write mode** (generates formatted files):
```starlark
buf_format(
    name = "format_files",
    srcs = ["api.proto"],
    write = True,
)
```

**Validation mode** (default - just checks formatting):
```starlark
buf_format(
    name = "format_validate",
    srcs = ["api.proto"],
)
```

#### Output Files

- `buf_format_diff.txt` - Formatting differences (diff mode)
- `formatted/*.proto` - Formatted proto files (write mode)
- `buf_format_check.txt` - Format validation results (validation mode)

### buf_breaking

Detects breaking changes in protobuf files by comparing against a baseline.

#### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `string` | required | Unique name for this breaking change target |
| `srcs` | `list[source]` | required | List of .proto files to check |
| `against` | `string` | required | Baseline to compare against |
| `config` | `dict[string, string]` | `{}` | Breaking change detection configuration |
| `buf_yaml` | `source` | `None` | Optional buf.yaml configuration file |
| `visibility` | `list[string]` | `["//visibility:private"]` | Buck2 visibility specification |

#### Baseline Types

**File baseline:**
```starlark
buf_breaking(
    name = "check_against_file",
    srcs = ["api.proto"],
    against = "baseline/api.proto",
)
```

**Git reference baseline:**
```starlark
buf_breaking(
    name = "check_against_main",
    srcs = ["api.proto"],
    against = "git#branch=main",
)
```

**Buck2 target baseline:**
```starlark
buf_breaking(
    name = "check_against_target",
    srcs = ["api.proto"],
    against = "//baseline:api_proto",
)
```

#### Configuration Options

```starlark
buf_breaking(
    name = "check_wire_compatible",
    srcs = ["api.proto"],
    against = "//baseline:api_proto",
    config = {
        "use": ["WIRE_COMPATIBLE"],
        "except": ["FIELD_SAME_DEFAULT"],
    },
)
```

#### Output Files

- `buf_breaking_report.json` - Machine-readable breaking change report
- `buf_breaking_report.txt` - Human-readable breaking change report

## Configuration

### buf.yaml Configuration

The buf rules support buf.yaml configuration files for centralized configuration:

```yaml
version: v1
name: buf.build/example/user
deps:
  - buf.build/googleapis/googleapis
lint:
  use:
    - DEFAULT
    - COMMENTS
    - FIELD_NAMES_LOWER_SNAKE_CASE
  except:
    - PACKAGE_VERSION_SUFFIX
  enum_zero_value_suffix: _UNSPECIFIED
  rpc_allow_same_request_response: false
breaking:
  use:
    - WIRE_COMPATIBLE
    - WIRE_JSON_COMPATIBLE
  except:
    - FIELD_SAME_DEFAULT
```

### Configuration Discovery

The buf rules feature comprehensive automatic configuration discovery that supports both simple modules and complex multi-module workspaces:

#### Discovery Algorithm

1. **Explicit `buf_yaml` attribute** (highest precedence)
2. **Rule `config` parameters** (override config file settings)
3. **Discovered `buf.work.yaml`** (workspace configuration)
4. **Discovered `buf.yaml`** (module configuration)
5. **Default configuration** (lowest precedence)

#### Supported Configuration Types

**Module Configuration Discovery:**
- Searches for `buf.yaml` files in proto directories and parent directories
- Walks up the directory tree until a configuration is found
- Uses the first `buf.yaml` discovered

**Workspace Configuration Discovery:**
- Searches for `buf.work.yaml` files for multi-module workspace support
- Automatically discovers and resolves module dependencies
- Supports both v1 and v2 buf configuration formats

**Hierarchical Search:**
- Starts from proto file locations and searches upward
- Supports nested directory structures
- Stops at the first configuration file found

#### Configuration Validation

The discovery system validates all discovered configurations:
- Schema validation for both v1 and v2 formats
- Dependency resolution verification
- Clear error messages for configuration issues
- Warning messages for deprecated settings

#### Examples

**Automatic Discovery:**
```starlark
buf_lint(
    name = "lint_api",
    srcs = ["api/v1/service.proto"],
    # Automatically discovers buf.yaml from parent directories
)
```

**Workspace Discovery:**
```starlark
buf_lint(
    name = "lint_workspace_module",
    srcs = ["workspace/module1/*.proto"],
    # Discovers buf.work.yaml and module-specific buf.yaml
)
```

**Override Discovery:**
```starlark
buf_lint(
    name = "lint_with_overrides",
    srcs = ["api.proto"],
    config = {
        "use": ["DEFAULT", "COMMENTS"],
        "enum_zero_value_suffix": "_UNKNOWN",
    },
    # Rule parameters override discovered config file settings
)
```

See `examples/buf-discovery/` for complete configuration discovery examples.

### Configuration Overrides

Inline `config` parameters override buf.yaml settings:

```starlark
buf_lint(
    name = "override_config",
    srcs = ["api.proto"],
    buf_yaml = "buf.yaml",  # Base configuration
    config = {
        "except": ["PACKAGE_VERSION_SUFFIX"],  # Override
    },
)
```

## Integration Patterns

### Proto Library Integration

Integrate buf validation with proto_library targets:

```starlark
load("//rules:proto.bzl", "proto_library")
load("//rules:buf.bzl", "buf_lint", "buf_format")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

buf_lint(
    name = "lint_user_proto",
    srcs = ["user.proto"],
    buf_yaml = "buf.yaml",
)

buf_format(
    name = "format_user_proto",
    srcs = ["user.proto"],
    diff = True,
)
```

### CI/CD Integration

Create validation targets for continuous integration:

```starlark
# Validation target that runs all buf checks
filegroup(
    name = "all_protos",
    srcs = glob(["**/*.proto"]),
)

buf_lint(
    name = "ci_lint",
    srcs = [":all_protos"],
    buf_yaml = "buf.yaml",
)

buf_format(
    name = "ci_format_check",
    srcs = [":all_protos"],
    diff = True,
)

buf_breaking(
    name = "ci_breaking_check",
    srcs = [":all_protos"],
    against = "git#branch=main",
)
```

### Multi-Module Projects

For projects with multiple buf modules:

```starlark
# Module 1
buf_lint(
    name = "lint_api_v1",
    srcs = ["api/v1/*.proto"],
    buf_yaml = "api/v1/buf.yaml",
)

# Module 2
buf_lint(
    name = "lint_api_v2",
    srcs = ["api/v2/*.proto"],
    buf_yaml = "api/v2/buf.yaml",
)
```

## Performance

### Caching

The buf rules leverage Buck2's caching system:

- **Input-based caching**: Results are cached based on proto file contents, configuration, and buf CLI version
- **Incremental validation**: Only changed files trigger re-validation
- **Cache invalidation**: Automatic invalidation when configuration or buf CLI version changes
- **Parallel execution**: Multiple buf operations can run in parallel

### Performance Tips

1. **Use specific source lists**: Only include files that need validation
2. **Leverage configuration files**: Use buf.yaml for consistent configuration
3. **Split large targets**: Break large proto sets into smaller, focused targets
4. **Use appropriate baselines**: Choose baselines that minimize breaking change detection overhead

## Troubleshooting

### Common Issues

**Empty srcs error:**
```
buf_lint: srcs cannot be empty
```
**Solution**: Ensure at least one .proto file is specified in srcs.

**Configuration validation error:**
```
Invalid buf configuration: lint.use must be a list
```
**Solution**: Check that configuration values are properly formatted.

**Missing baseline error:**
```
buf_breaking: against parameter is required
```
**Solution**: Specify a valid baseline for breaking change detection.

### Debug Output

Enable verbose output for troubleshooting:

```bash
buck2 build //path:target --verbose=1
```

### Common Configuration Issues

**Import path problems:**
- Ensure proto files can import their dependencies
- Check that buf.yaml deps are correctly specified
- Verify import paths match package structure

**Lint rule conflicts:**
- Review lint rule combinations in buf.yaml
- Use `except` to exclude conflicting rules
- Test configuration with buf CLI directly

## Advanced Usage

### Custom Lint Rules

Extend linting with custom rules:

```starlark
buf_lint(
    name = "custom_lint",
    srcs = ["api.proto"],
    config = {
        "use": ["DEFAULT"],
        "ignore": ["deprecated/*.proto"],
        "enum_zero_value_suffix": "_UNKNOWN",
    },
)
```

### Breaking Change Policies

Implement different breaking change policies:

```starlark
# Strict wire compatibility
buf_breaking(
    name = "strict_breaking",
    srcs = ["api.proto"],
    against = "//baseline:api_proto",
    config = {"use": ["WIRE_COMPATIBLE"]},
)

# JSON compatibility
buf_breaking(
    name = "json_breaking",
    srcs = ["api.proto"],
    against = "//baseline:api_proto",
    config = {"use": ["WIRE_JSON_COMPATIBLE"]},
)
```

### Integration with Other Tools

Combine buf rules with other protobuf tools:

```starlark
# Validate with buf, then generate code
buf_lint(
    name = "validate_api",
    srcs = ["api.proto"],
)

go_proto_library(
    name = "api_go",
    srcs = ["api.proto"],
    deps = [":validate_api"],  # Ensure validation passes first
)
```

## Migration Guide

### From protoc-based Validation

If migrating from protoc-based validation:

1. **Replace protoc lint actions** with buf_lint rules
2. **Add buf.yaml configuration** for consistent settings
3. **Update CI pipelines** to use new buf targets
4. **Configure breaking change detection** for API evolution

### From External buf CLI

If already using buf CLI externally:

1. **Remove manual buf CLI calls** from scripts
2. **Convert buf.yaml configurations** to Buck2 rules
3. **Update build dependencies** to use buf rule outputs
4. **Leverage Buck2 caching** for improved performance

## Examples

Complete examples are available in the `examples/buf/` directory:

- `examples/buf/BUCK` - Comprehensive rule usage examples
- `examples/buf/user.proto` - Example protobuf service definition
- `examples/buf/user_types.proto` - Example protobuf types
- `examples/buf/buf.yaml` - Example buf configuration

## Related Documentation

- [Buck2 Rule Authoring Guide](https://buck2.build/docs/rule_authoring/)
- [Buf CLI Reference](https://docs.buf.build/reference/cli/)
- [Protocol Buffers Language Guide](https://developers.google.com/protocol-buffers/docs/proto3)
- [Buck2 Protobuf Rules](./rules-reference.md)

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review existing [GitHub issues](https://github.com/your-org/buck2-protobuf/issues)
3. Create a new issue with detailed reproduction steps
4. Consult the buf CLI documentation for buf-specific questions
