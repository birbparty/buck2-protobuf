# Buf Configuration Discovery Examples

This directory demonstrates the automatic buf configuration discovery functionality implemented in buck2-protobuf. The discovery system automatically finds and uses buf.yaml and buf.work.yaml configuration files, supporting both simple modules and complex multi-module workspaces.

## Discovery Features

### ✅ Automatic Configuration Discovery
- **buf.yaml** - Module-level configuration discovery
- **buf.work.yaml** - Workspace-level configuration discovery  
- **Hierarchical Search** - Searches up directory tree for configuration files
- **Configuration Validation** - Validates discovered configurations with clear error messages
- **Rule Override Support** - Rule parameters take precedence over config files

### ✅ Supported Scenarios
- **Simple Module** - Single buf.yaml file with proto files
- **Nested Directories** - Proto files in subdirectories discover parent configs
- **Multi-Module Workspace** - buf.work.yaml with multiple module directories
- **Explicit Configuration** - Override discovery with explicit buf_yaml parameter
- **Rule Parameter Overrides** - Inline config parameters override file settings

## Examples Overview

### 1. Simple Configuration Discovery (`simple.proto`)
```starlark
buf_lint(
    name = "lint_simple",
    srcs = ["simple.proto"],
    # No buf_yaml specified - automatically discovers buf.yaml
)
```
**Discovery**: Finds `buf.yaml` in the same directory and uses its configuration.

### 2. Rule Parameter Overrides (`api.proto`)
```starlark
buf_lint(
    name = "lint_with_overrides", 
    srcs = ["api.proto"],
    config = {
        "use": ["DEFAULT", "COMMENTS", "FIELD_NAMES_LOWER_SNAKE_CASE"],
        "except": ["PACKAGE_VERSION_SUFFIX"],
        "enum_zero_value_suffix": "_UNKNOWN",
    },
    # Rule parameters override buf.yaml settings
)
```
**Discovery**: Finds `buf.yaml` but rule parameters take precedence for lint configuration.

### 3. Hierarchical Configuration Discovery (`api/v1/*.proto`)
```starlark
buf_lint(
    name = "lint_nested",
    srcs = ["api/v1/service.proto", "api/v1/types.proto"],
    # Proto files in subdirectory discover config from parent
)
```
**Discovery**: Proto files in `api/v1/` directory discover `buf.yaml` from parent directory.

### 4. Explicit Configuration File (`custom.proto`)
```starlark
buf_format(
    name = "format_explicit_config",
    srcs = ["custom.proto"],
    buf_yaml = "custom-buf.yaml",
    # Explicit config file takes highest precedence
)
```
**Discovery**: Uses explicitly specified `custom-buf.yaml` instead of automatic discovery.

### 5. Multi-Module Workspace (`workspace/`)
```starlark
buf_lint(
    name = "lint_workspace_module",
    srcs = ["workspace/module1/*.proto"],
    # Discovers buf.work.yaml and module-specific buf.yaml
)
```
**Discovery**: 
1. Finds `workspace/buf.work.yaml` (workspace config)
2. Finds `workspace/module1/buf.yaml` (module config)
3. Merges configurations appropriately

## Configuration Files

### Main Module Configuration (`buf.yaml`)
```yaml
version: v1
name: buf.build/buck2-protobuf/discovery-examples
deps:
  - buf.build/googleapis/googleapis
  - oras.birb.homes/common/types
lint:
  use:
    - DEFAULT
    - COMMENTS
    - FIELD_NAMES_LOWER_SNAKE_CASE
  except:
    - PACKAGE_VERSION_SUFFIX
  enum_zero_value_suffix: _UNSPECIFIED
breaking:
  use:
    - WIRE_COMPATIBLE
    - WIRE_JSON_COMPATIBLE
```

### Custom Configuration (`custom-buf.yaml`)
```yaml
version: v1
name: buf.build/buck2-protobuf/custom-config
lint:
  use:
    - DEFAULT
    - UNARY_RPC
  except:
    - ENUM_ZERO_VALUE_SUFFIX
  enum_zero_value_suffix: _NONE
  service_suffix: API
```

### Workspace Configuration (`workspace/buf.work.yaml`)
```yaml
version: v1
directories:
  - module1
  - module2
```

## Discovery Algorithm

The configuration discovery follows this priority order:

1. **Explicit buf_yaml parameter** (highest precedence)
2. **Rule config parameters** (override config file settings)
3. **Discovered buf.work.yaml** (workspace configuration)
4. **Discovered buf.yaml** (module configuration)
5. **Default configuration** (lowest precedence)

### Discovery Process
```
1. Check for explicit buf_yaml parameter
2. If not found, search for buf.work.yaml (workspace mode)
   - Search up directory tree from proto file locations
   - Parse workspace config and find module directories
3. If no workspace config, search for buf.yaml (module mode)
   - Search up directory tree from proto file locations
   - Use first buf.yaml found
4. Apply rule parameter overrides
5. Validate final merged configuration
```

## Running the Examples

```bash
# Lint with automatic discovery
buck2 run //examples/buf-discovery:lint_simple

# Format with rule overrides
buck2 run //examples/buf-discovery:lint_with_overrides

# Test hierarchical discovery
buck2 run //examples/buf-discovery:lint_nested

# Use explicit config
buck2 run //examples/buf-discovery:format_explicit_config

# Workspace example
buck2 run //examples/buf-discovery:lint_workspace_module
```

## Integration with ORAS Registry

The discovery system supports dependencies from both BSR and ORAS registries:

```yaml
deps:
  - buf.build/googleapis/googleapis    # BSR dependency
  - oras.birb.homes/common/types      # ORAS registry dependency
```

This enables seamless integration with the `oras.birb.homes` registry for internal dependencies while maintaining compatibility with public BSR modules.

## Error Handling

The discovery system provides clear error messages for common issues:

- **Missing configuration**: Uses default configuration with warning
- **Invalid configuration**: Reports validation errors with fix suggestions
- **Dependency conflicts**: Shows dependency resolution issues
- **Permission errors**: Clear messages about file access problems

## Performance

Configuration discovery is optimized for performance:
- **Caching**: Discovered configurations are cached to avoid repeated file system access
- **Efficient search**: Stops searching once configuration is found
- **Minimal overhead**: Discovery adds minimal build time overhead
- **Incremental builds**: Cached results work with Buck2's incremental build system

## Best Practices

1. **Place buf.yaml close to proto files** for fastest discovery
2. **Use workspace configuration** for multi-module projects
3. **Override selectively** - only override specific settings you need to change
4. **Validate configurations** regularly to catch issues early
5. **Document custom configurations** for team clarity

This discovery system enables seamless buf integration with existing buf projects while providing the flexibility to override settings as needed for specific build targets.
