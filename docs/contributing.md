# Contributing Guide

Welcome to the Buck2 protobuf integration project! This guide will help you contribute effectively to the codebase.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

### Prerequisites

- **Buck2** >= 2023.11.01
- **Python** >= 3.8 (for development scripts)
- **Go** >= 1.21 (for Go rule testing)
- **Node.js** >= 18 (for TypeScript rule testing)
- **Rust** >= 1.70 (for Rust rule testing)
- **C++** compiler (GCC >= 9 or Clang >= 10)

### Initial Setup

```bash
# Fork and clone the repository
git clone git@github.com:birbparty/buck2-protobuf.git
cd buck2-protobuf

# Set up development environment
./scripts/setup-dev.sh

# Verify setup
buck2 test //test/...
```

---

## Development Environment

### Directory Structure

```
buck2-protobuf/
├── rules/                   # Core Starlark rule implementations
│   ├── proto.bzl           # Main protobuf rules
│   ├── go.bzl              # Go-specific rules
│   ├── python.bzl          # Python-specific rules
│   ├── typescript.bzl      # TypeScript-specific rules
│   ├── cpp.bzl             # C++ specific rules
│   ├── rust.bzl            # Rust-specific rules
│   └── private/            # Internal implementation details
├── tools/                  # Tool management and utilities
├── test/                   # Test infrastructure and test cases
├── examples/               # Usage examples for documentation
├── docs/                   # Documentation files
├── qa/                     # Quality assurance framework
└── scripts/                # Development and CI scripts
```

### Key Files

| File | Purpose |
|------|---------|
| `rules/proto.bzl` | Core protobuf rules (proto_library, proto_bundle, grpc_service) |
| `rules/private/providers.bzl` | Provider definitions for inter-rule communication |
| `rules/private/utils.bzl` | Shared utility functions |
| `tools/platforms/common.bzl` | Platform detection and tool management |
| `test/rules/` | Unit tests for each rule implementation |
| `test/integration/` | End-to-end integration tests |

---

## Project Structure

### Rule Architecture

The project follows a layered architecture:

```
┌─────────────────────────────────────┐
│          Public API Rules          │  (rules/*.bzl)
├─────────────────────────────────────┤
│        Private Implementation      │  (rules/private/*.bzl)
├─────────────────────────────────────┤
│           Tool Management          │  (tools/*.py, tools/platforms/*.bzl)
├─────────────────────────────────────┤
│         Platform Detection         │  (platforms/*.bzl)
└─────────────────────────────────────┘
```

### Provider System

Rules communicate through structured providers:

```python
# Core providers
ProtoInfo = provider(fields = {
    "descriptor_set": "File",
    "proto_files": "list[File]", 
    "import_paths": "list[string]",
    # ... transitive fields
})

LanguageProtoInfo = provider(fields = {
    "language": "string",
    "generated_files": "list[File]",
    "package_name": "string",
    "dependencies": "list[string]",
})
```

---

## Development Workflow

### 1. Creating New Rules

When adding a new language or feature:

```python
# 1. Define the public API in rules/{language}.bzl
def new_language_proto_library(name, proto, **kwargs):
    """Public rule for new language generation."""
    new_language_proto_library_rule(
        name = name,
        proto = proto,
        **kwargs
    )

# 2. Implement the rule logic
def _new_language_proto_library_impl(ctx):
    # Get ProtoInfo from dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Generate code using protoc
    output_files = _generate_code(ctx, proto_info)
    
    # Create language-specific provider
    lang_info = LanguageProtoInfo(
        language = "new_language",
        generated_files = output_files,
        # ...
    )
    
    return [DefaultInfo(default_outputs = output_files), lang_info]

# 3. Define the rule
new_language_proto_library_rule = rule(
    impl = _new_language_proto_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo]),
        # ... other attributes
    },
)
```

### 2. Adding Tests

Every new rule requires comprehensive tests:

```python
# test/rules/new_language_proto_test.bzl
load("@prelude//utils:buck_testing.bzl", "buck_test")
load("//rules:new_language.bzl", "new_language_proto_library")
load("//test:test_utils.bzl", "assert_files_exist", "assert_content_contains")

def test_basic_generation():
    """Test basic protobuf code generation."""
    new_language_proto_library(
        name = "test_basic",
        proto = "//test/fixtures:simple_proto",
    )
    
    # Verify expected files are generated
    assert_files_exist([
        "test_basic/simple.new_lang",
        "test_basic/package.new_lang",
    ])
    
    # Verify content correctness
    assert_content_contains(
        "test_basic/simple.new_lang",
        "class SimpleMessage",
    )

buck_test(
    name = "new_language_proto_test",
    srcs = ["new_language_proto_test.bzl"],
    deps = [
        "//rules:new_language",
        "//test:test_utils",
    ],
)
```

### 3. Documentation Updates

Update documentation for any new features:

```python
# Add to docs/rules-reference.md
### new_language Rules

#### new_language_proto_library

Generates NewLanguage code from a `proto_library` target.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Target name |
| `proto` | `string` | ✅ | Proto library target |
| `package_name` | `string` | ❌ | Package override |

**Example:**
```python
new_language_proto_library(
    name = "user_new_lang",
    proto = ":user_proto",
    package_name = "com.org.user",
    visibility = ["PUBLIC"],
)
```
```

---

## Testing

### Test Categories

1. **Unit Tests** (`test/rules/`)
   - Test individual rule implementations
   - Verify provider creation and parameter handling
   - Fast feedback for development

2. **Integration Tests** (`test/integration/`)
   - End-to-end workflow testing
   - Cross-language compatibility
   - Performance benchmarking

3. **Example Tests** (`examples/*/`)
   - Verify documentation examples work
   - Real-world usage patterns
   - User-facing API validation

### Running Tests

```bash
# Run all tests
buck2 test //test/...

# Run specific test categories
buck2 test //test/rules/...          # Unit tests only
buck2 test //test/integration/...    # Integration tests only
buck2 test //examples/...            # Example validation

# Run tests for specific language
buck2 test //test/rules:go_proto_test
buck2 test //test/integration:test_go_compilation

# Run performance tests
buck2 run //test/performance:benchmark_suite

# Run with verbose output
buck2 test //test/... -v 2
```

### Writing New Tests

Follow these patterns for consistent testing:

```python
# test/rules/example_test.bzl
load("//test:test_utils.bzl", "proto_test_suite")

def test_basic_functionality():
    """Test description explaining what this verifies."""
    # Setup
    test_target = create_test_target()
    
    # Execute
    result = build_target(test_target)
    
    # Verify
    assert_success(result)
    assert_files_generated(result.outputs, expected_files)
    assert_content_correct(result.outputs)

def test_error_conditions():
    """Test error handling and validation."""
    with assert_failure():
        invalid_target = create_invalid_target()
        build_target(invalid_target)

# Register tests
proto_test_suite(
    name = "example_test_suite",
    tests = [
        test_basic_functionality,
        test_error_conditions,
    ],
)
```

---

## Code Style

### Starlark Style

Follow [Starlark style guide](https://bazel.build/rules/bzl-style) with these additions:

```python
# ✅ Good: Clear function names and documentation
def generate_language_specific_code(ctx, proto_info, language_config):
    """
    Generates language-specific code from protobuf definitions.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider with proto file information
        language_config: Dictionary with language-specific configuration
        
    Returns:
        List of generated file objects
    """
    # Implementation...

# ✅ Good: Descriptive variable names
generated_source_files = []
protoc_command_args = cmd_args()
output_directory = ctx.actions.declare_output("generated")

# ❌ Poor: Unclear names and missing documentation
def gen_code(ctx, info, cfg):
    files = []
    cmd = cmd_args()
    # ...

# ✅ Good: Consistent parameter formatting
rule_definition = rule(
    impl = _implementation_function,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "language_options": attrs.dict(
            attrs.string(), 
            attrs.string(), 
            default = {}, 
            doc = "Language-specific options"
        ),
        "visibility": attrs.list(attrs.string(), default = ["//visibility:private"]),
    },
)
```

### Python Style

Follow [PEP 8](https://peps.python.org/pep-0008/) for Python scripts:

```python
#!/usr/bin/env python3
"""Tool management utilities for the protobuf Buck2 integration.

This module provides functions for downloading, validating, and managing
protoc and language-specific protobuf plugins across different platforms.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional


class ToolManager:
    """Manages protobuf tool downloads and validation."""
    
    def __init__(self, cache_dir: Path) -> None:
        """Initialize tool manager with cache directory."""
        self.cache_dir = cache_dir
        self.tools: Dict[str, str] = {}
    
    def download_tool(self, tool_name: str, version: str) -> Path:
        """Download and cache a specific tool version."""
        # Implementation...
```

### Documentation Style

Use clear, concise documentation:

```python
def proto_library(
    name: str,
    srcs: list[str],
    deps: list[str] = [],
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Defines a protobuf library from .proto source files.
    
    This rule creates a protobuf library that can be consumed by language-specific
    generation rules. It handles proto file validation, dependency resolution,
    and creates the necessary artifacts for downstream code generation.
    
    Args:
        name: Unique name for this protobuf library target
        srcs: List of .proto files to include in this library
        deps: List of proto_library targets this library depends on
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        proto_library(
            name = "user_proto",
            srcs = ["user.proto", "user_types.proto"],
            deps = ["//common:base_proto"],
            visibility = ["PUBLIC"],
        )
    """
```

---

## Documentation

### Documentation Requirements

All contributions must include appropriate documentation:

1. **API Documentation**: Function/rule docstrings with examples
2. **User Documentation**: Updates to relevant guides in `docs/`
3. **Example Code**: Working examples in `examples/`
4. **Test Documentation**: Clear test descriptions and coverage

### Documentation Format

Use Markdown with consistent formatting:

```markdown
# Rule Name

Brief description of what this rule does.

## Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Parameter description |
| `optional_param` | `string` | ❌ | Optional parameter (default: "value") |

## Example

```python
rule_name(
    name = "example",
    required_param = "value",
    optional_param = "custom_value",
    visibility = ["PUBLIC"],
)
```

## Generated Files

- `output.ext` - Description of generated file
- `package.ext` - Description of package file
```

### Updating Documentation

When making changes that affect user-facing APIs:

1. Update relevant sections in `docs/rules-reference.md`
2. Add troubleshooting entries to `docs/troubleshooting.md` if needed
3. Update performance implications in `docs/performance.md`
4. Add migration notes to `docs/migration-guide.md` for breaking changes
5. Update examples in `examples/` directories
6. Update main `README.md` if adding major features

---

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
   ```bash
   buck2 test //test/...
   ```

2. **Check Code Style**: Run linting and formatting
   ```bash
   ./scripts/lint.sh
   ./scripts/format.sh
   ```

3. **Update Documentation**: Add/update relevant documentation

4. **Performance Testing**: Run performance benchmarks for significant changes
   ```bash
   buck2 run //test/performance:benchmark_suite
   ```

### Pull Request Template

```markdown
## Description

Brief description of changes and motivation.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Performance tests pass (if applicable)
- [ ] Examples validate

## Documentation

- [ ] API documentation updated
- [ ] User guides updated
- [ ] Examples added/updated
- [ ] Migration notes added (if breaking change)

## Checklist

- [ ] My code follows the project style guidelines
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and quality checks
2. **Code Review**: Maintainers review code for:
   - Correctness and functionality
   - Code style and best practices
   - Documentation completeness
   - Test coverage
   - Performance implications
3. **Feedback**: Address review comments and update PR
4. **Approval**: Get approval from maintainers
5. **Merge**: Squash and merge into main branch

### Commit Message Format

Use conventional commit format:

```
type(scope): brief description

Longer description if needed, explaining what and why.

Fixes #123
Closes #456
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Formatting, no code change
- `refactor`: Code refactoring
- `test`: Adding/updating tests
- `perf`: Performance improvements
- `ci`: CI/CD changes

**Examples:**
```
feat(go): add support for Go modules in go_proto_library

Add go_module parameter to go_proto_library rule that generates
go.mod files with correct dependencies for better Go module
integration.

Fixes #234

test(integration): add cross-language compatibility tests

Add integration tests that verify generated code from different
languages can interoperate correctly.

docs(api): update proto_bundle documentation

Add examples and clarify parameter descriptions for proto_bundle
rule in the API reference.
```

---

## Development Scripts

### Available Scripts

| Script | Purpose |
|--------|---------|
| `scripts/setup-dev.sh` | Set up development environment |
| `scripts/test.sh` | Run comprehensive test suite |
| `scripts/lint.sh` | Run code linting |
| `scripts/format.sh` | Format code according to style guide |
| `scripts/benchmark.sh` | Run performance benchmarks |
| `scripts/update-tools.sh` | Update tool versions and checksums |

### Running Quality Checks

```bash
# Full quality check suite
./scripts/quality-check.sh

# Individual checks
./scripts/lint.sh           # Code style
./scripts/test.sh           # All tests
./scripts/benchmark.sh      # Performance
./scripts/security-scan.sh  # Security analysis
```

---

## Getting Help

### Resources

- **Documentation**: Start with `docs/` directory
- **Examples**: Check `examples/` for working code
- **Tests**: Look at `test/` for usage patterns
- **Issues**: Search existing GitHub issues

### Communication

- **Discussions**: Use GitHub Discussions for questions
- **Issues**: Create GitHub issues for bugs/feature requests
- **Pull Requests**: Use PR comments for code-specific questions

### Common Questions

**Q: How do I add support for a new language?**
A: See the "Creating New Rules" section above and examine existing language implementations in `rules/`.

**Q: How do I test my changes?**
A: Run `buck2 test //test/...` for unit tests and `buck2 test //test/integration/...` for integration tests.

**Q: My tests are failing, what should I check?**
A: Check the [Troubleshooting Guide](troubleshooting.md) and ensure your development environment is set up correctly.

**Q: How do I add a new protoc plugin?**
A: Update the tool management system in `tools/` and add plugin configuration to the relevant language rule.

---

Thank you for contributing to the Buck2 protobuf integration! Your contributions help make this tool better for the entire community.
