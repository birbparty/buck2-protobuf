# 🎯 Quickstart Examples

These examples provide a gentle introduction to buf integration with buck2-protobuf. Start here if you're new to buf or want to understand the basics.

## Examples Overview

### 1. Basic Linting (`basic-lint/`)
Simple buf_lint example showing fundamental linting setup and common rules.

### 2. Code Formatting (`formatting/`)
Demonstrates buf_format for consistent code style and CI integration.

### 3. Breaking Changes (`breaking/`)
Introduction to buf_breaking for API compatibility validation.

### 4. Configuration Discovery (`config-discovery/`)
Shows automatic buf.yaml discovery and rule customization.

### 5. BSR Dependencies (`bsr-deps/`)
Basic usage of Buf Schema Registry dependencies.

## Learning Path

1. **Start with `basic-lint/`** to understand linting fundamentals
2. **Progress to `formatting/`** to learn code style enforcement
3. **Explore `breaking/`** to understand compatibility checking
4. **Try `config-discovery/`** to see automatic configuration
5. **Finish with `bsr-deps/`** to learn dependency management

## Quick Commands

```bash
# Run all quickstart examples
buck2 build //examples/buf-integration/quickstart/...

# Run specific examples
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_simple
buck2 run //examples/buf-integration/quickstart/formatting:format_check
buck2 run //examples/buf-integration/quickstart/breaking:breaking_check
```

## Key Concepts Covered

### 🔍 Linting Fundamentals
- Default lint rules and their purpose
- Common rule customizations
- Error interpretation and fixing
- Best practices for API design

### 🎨 Code Formatting
- Automatic formatting with buf_format
- CI integration patterns
- Consistent style enforcement
- Format checking vs. auto-fixing

### 🚫 Breaking Change Detection
- Wire compatibility vs. source compatibility
- Safe vs. unsafe changes
- Baseline establishment
- Change approval workflows

### ⚙️ Configuration Management
- buf.yaml discovery and structure
- Rule parameter overrides
- Project-specific customizations
- Configuration inheritance

### 📦 Dependency Management
- BSR public repository usage
- Version specification patterns
- Dependency resolution caching
- Common public dependencies

## Success Criteria

After completing these examples, you should be able to:

- ✅ Set up basic buf linting for your protobuf files
- ✅ Integrate buf formatting into your development workflow
- ✅ Understand and prevent breaking changes in your APIs
- ✅ Configure buf rules to match your project's requirements
- ✅ Use popular BSR dependencies in your protobuf definitions

## Next Steps

Once you've mastered these quickstart examples:

1. **[API Evolution](../api-evolution/)** - Learn advanced versioning strategies
2. **[Multi-Service](../multi-service/)** - Explore microservices patterns
3. **[ORAS Registry](../oras-registry/)** - Set up private registries
4. **[Advanced Features](../advanced-features/)** - Custom plugins and optimization

## Troubleshooting

### Common Issues

**Linting Errors:**
```bash
# View detailed lint output
buck2 run //examples/buf-integration/quickstart/basic-lint:lint_simple --verbose

# Check specific rule documentation
buf lint --help
```

**Format Issues:**
```bash
# See format differences
buck2 run //examples/buf-integration/quickstart/formatting:format_diff

# Auto-fix formatting
buck2 run //examples/buf-integration/quickstart/formatting:format_write
```

**Breaking Change Issues:**
```bash
# Understand breaking change details
buck2 run //examples/buf-integration/quickstart/breaking:breaking_detailed

# Review breaking change documentation
buf breaking --help
```

### Getting Help

- **Documentation**: See individual example directories for detailed explanations
- **Rules Reference**: Check `//docs/buf-rules.md` for complete rule documentation
- **Best Practices**: Review `//examples/buf-integration/best-practices/` for production patterns

---

**Start with these quickstart examples to build a solid foundation in buf integration! 🚀**
