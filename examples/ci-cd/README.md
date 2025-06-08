# 🚀 CI/CD Integration Patterns

This directory provides comprehensive CI/CD examples for automating protobuf workflows with Buck2, featuring ORAS registry integration, governance enforcement, and multi-platform support.

## 📁 Directory Structure

```
examples/ci-cd/
├── README.md                          # This file
├── github-actions/                    # GitHub Actions workflows
│   ├── protobuf-validation.yml        # PR validation workflow
│   ├── oras-publishing.yml            # ORAS registry publishing
│   ├── breaking-change-detection.yml  # Breaking change detection
│   ├── multi-platform-ci.yml          # Cross-platform testing
│   ├── workspace-validation.yml       # Full workspace validation
│   └── governance-enforcement.yml     # Optional governance workflows
├── gitlab-ci/                         # GitLab CI examples
│   └── .gitlab-ci.yml
├── jenkins/                           # Jenkins pipeline examples
│   └── Jenkinsfile
├── azure-pipelines/                   # Azure DevOps examples
│   └── azure-pipelines.yml
└── scripts/                           # CI automation scripts
    ├── ci_validation.py               # Validation automation
    ├── oras_deploy.py                 # ORAS deployment helpers
    └── validate_workflows.py          # Workflow testing tools
```

## 🎯 Key Features

### ✅ ORAS-First Strategy
- Primary examples target ORAS registries (`oras.birb.homes`)
- Seamless integration with existing Buck2 publishing rules
- Multi-registry publishing patterns (ORAS + BSR backup)

### ✅ GitHub Actions Integration
- Comprehensive workflow examples for protobuf projects
- Multi-platform CI/CD (Linux, macOS, Windows)
- Automated schema validation and publishing
- Breaking change detection with governance integration

### ✅ Governance Integration
- Optional schema review enforcement
- Breaking change policy automation
- Team notification workflows
- Audit logging and compliance tracking

### ✅ Buck2 Native Workflows
- Direct integration with existing governance rules
- Leverages `//rules/governance.bzl` and `//rules/bsr_publish.bzl`
- Seamless validation and publishing automation

## 🚀 Quick Start

### 1. GitHub Actions Setup

Copy the desired workflow from `github-actions/` to your repository's `.github/workflows/` directory:

```bash
# Basic protobuf validation
cp examples/ci-cd/github-actions/protobuf-validation.yml .github/workflows/

# ORAS publishing on releases
cp examples/ci-cd/github-actions/oras-publishing.yml .github/workflows/
```

### 2. Configure Registry Authentication

Set up ORAS registry authentication in your repository settings:

```bash
# Repository secrets
ORAS_USERNAME=your-username
ORAS_PASSWORD=your-password
ORAS_REGISTRY=oras.birb.homes
```

### 3. Enable Governance (Optional)

To enable schema governance and review workflows:

```bash
# Set repository variable
ENABLE_GOVERNANCE=true

# Configure reviewers in governance.yaml
reviewers:
  - "@platform-team"
  - "@schema-owners"
```

## 🔧 Workflow Examples

### Basic PR Validation
```yaml
# .github/workflows/protobuf-validation.yml
name: Protobuf Validation
on:
  pull_request:
    paths: ['**/*.proto']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Buck2
        # Buck2 installation steps
      - name: Validate Schemas
        run: buck2 run //schemas:validate_all
```

### ORAS Publishing
```yaml
# .github/workflows/oras-publishing.yml
name: Publish to ORAS
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: oras-project/setup-oras@v1
      - name: Publish Schemas
        run: buck2 run //schemas:publish_oras
        env:
          ORAS_REGISTRY: ${{ secrets.ORAS_REGISTRY }}
```

## 🛠️ Customization

### Registry Configuration

Modify publishing targets in your `BUCK` files:

```python
# examples/your-project/BUCK
load("//rules:bsr_publish.bzl", "bsr_publish")

bsr_publish(
    name = "publish_schemas",
    proto = ":my_schemas",
    repositories = {
        "primary": "oras.birb.homes/myorg/schemas",
        "backup": "buf.build/myorg/schemas"
    },
    version_strategy = "semantic",
)
```

### Governance Integration

Enable optional governance in your workflows:

```python
# examples/your-project/BUCK
load("//rules:governance.bzl", "schema_review", "bsr_breaking_check")

schema_review(
    name = "review_schemas",
    proto = ":my_schemas",
    reviewers = [],  # Configure as needed
    approval_count = 1,
    auto_approve_minor = True,
)

bsr_breaking_check(
    name = "check_breaking",
    proto = ":my_schemas",
    against_repository = "oras.birb.homes/myorg/schemas",
    breaking_policy = "warn",  # or "error", "require_approval"
)
```

## 🌐 Platform Coverage

### GitHub Actions ⭐ (Primary)
- Complete workflow examples with Buck2 integration
- Multi-platform CI (Linux, macOS, Windows)
- ORAS publishing automation
- Governance enforcement patterns

### GitLab CI
- Basic validation and publishing workflows
- Docker-based Buck2 execution
- ORAS registry integration

### Jenkins
- Pipeline examples with Buck2
- Multi-stage validation and deployment
- Enterprise integration patterns

### Azure Pipelines
- Basic protobuf validation workflows
- Windows-first examples
- Azure Container Registry integration

## 📚 Advanced Patterns

### Multi-Platform CI
```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    include:
      - os: ubuntu-latest
        buck2-platform: linux
      - os: macos-latest
        buck2-platform: darwin
      - os: windows-latest
        buck2-platform: windows
```

### Conditional Governance
```yaml
- name: Schema Review
  if: env.ENABLE_GOVERNANCE == 'true'
  run: buck2 run //schemas:review_check
```

### Atomic Multi-Registry Publishing
```yaml
- name: Publish to Multiple Registries
  run: |
    buck2 run //schemas:publish_oras_primary
    buck2 run //schemas:publish_bsr_backup
```

## 🔒 Security Best Practices

### Registry Authentication
- Use repository secrets for credentials
- Rotate tokens regularly
- Implement least-privilege access

### Workflow Security
- Pin action versions with SHA
- Use workflow isolation
- Implement approval workflows for releases

### Audit and Compliance
- Enable workflow logging
- Track schema publications
- Implement change notifications

## 🚨 Troubleshooting

### Common Issues

**Buck2 Installation Issues:**
- Ensure correct platform detection
- Use official Buck2 releases
- Cache Buck2 binaries for faster CI

**ORAS Authentication:**
- Verify registry credentials
- Check network connectivity
- Validate registry URL format

**Schema Validation Failures:**
- Review breaking change policies
- Check governance configuration
- Validate proto syntax

### Debug Commands
```bash
# Validate locally
buck2 run //schemas:validate_all

# Test ORAS publishing
buck2 run //schemas:publish_oras -- --dry-run

# Check governance status
buck2 run //schemas:governance_check
```

## 🤝 Contributing

When adding new CI/CD patterns:

1. **Test Thoroughly**: Validate on multiple platforms
2. **Document Clearly**: Include setup and configuration steps
3. **Follow Patterns**: Use existing governance integration
4. **Security First**: Implement secure credential handling

## 📖 Related Documentation

- [Buck2 Rules Reference](../../docs/rules-reference.md)
- [ORAS Registry Setup](../../docs/oras-client.md)
- [Schema Governance](../../docs/governance.md)
- [BSR Publishing](../../docs/bsr-publishing.md)

---

**Ready to automate your protobuf workflows? Start with the GitHub Actions examples and customize for your team's needs! 🎉**
