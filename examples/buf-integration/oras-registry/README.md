# 🚀 ORAS Registry Integration Examples

This directory demonstrates advanced ORAS registry integration with `oras.birb.homes`, showcasing how to use private registries alongside public BSR dependencies for enterprise-grade protobuf development.

## What You'll Learn

- Private ORAS registry setup and usage
- Hybrid BSR + ORAS dependency management
- Team collaboration workflows
- Performance optimization with ORAS caching
- Authentication and security patterns

## Examples Overview

### 1. Private Dependencies (`private-deps/`)
Using internal protobuf modules from `oras.birb.homes` registry.

### 2. Hybrid Registries (`hybrid-registries/`)
Combining public BSR dependencies with private ORAS modules.

### 3. Team Workflows (`team-workflows/`)
Multi-team development patterns with shared internal dependencies.

### 4. Performance Testing (`performance/`)
Optimizing build performance with ORAS caching strategies.

## Example Structure

```
oras-registry/
├── README.md                       # This documentation
├── private-deps/                   # Private registry usage
│   ├── BUCK
│   ├── service.proto
│   ├── buf.yaml
│   └── README.md
├── hybrid-registries/              # BSR + ORAS combination
│   ├── BUCK
│   ├── api_service.proto
│   ├── buf.yaml
│   └── README.md
├── team-workflows/                 # Multi-team patterns
│   ├── BUCK
│   ├── team-a-service.proto
│   ├── team-b-service.proto
│   ├── shared-types.proto
│   ├── buf.yaml
│   └── README.md
└── performance/                    # Performance optimization
    ├── BUCK
    ├── large_service.proto
    ├── buf.yaml
    └── README.md
```

## ORAS Registry Benefits

### 🏢 Enterprise Features
- **Private Modules**: Keep internal APIs secure and controlled
- **Team Isolation**: Separate namespaces for different teams
- **Version Control**: Full control over module versioning and releases
- **Access Control**: Fine-grained permissions and authentication

### ⚡ Performance Advantages
- **Content Deduplication**: ORAS's content-addressable storage reduces bandwidth
- **Parallel Resolution**: Multiple dependencies resolved simultaneously
- **Team Caching**: Shared cache across team members reduces build times
- **Incremental Updates**: Only changed content is transferred

### 🔒 Security & Compliance
- **Private Hosting**: Keep sensitive schemas within your infrastructure
- **Audit Trails**: Track all dependency usage and changes
- **Access Policies**: Control who can publish and consume modules
- **Compliance**: Meet regulatory requirements for data handling

## Quick Start

### 1. Private Registry Setup
```bash
# Navigate to private dependencies example
cd examples/buf-integration/oras-registry/private-deps/

# Build with private ORAS dependencies
buck2 build //:internal_service_proto
```

### 2. Hybrid Registry Usage
```bash
# Navigate to hybrid example
cd examples/buf-integration/oras-registry/hybrid-registries/

# Build with both BSR and ORAS dependencies
buck2 build //:hybrid_api_proto
```

### 3. Team Workflow Testing
```bash
# Navigate to team workflows example
cd examples/buf-integration/oras-registry/team-workflows/

# Build multi-team services
buck2 build //team-a:service_proto
buck2 build //team-b:service_proto
buck2 build //shared:types_proto
```

### 4. Performance Benchmarking
```bash
# Navigate to performance example
cd examples/buf-integration/oras-registry/performance/

# Run performance tests
buck2 run //:performance_test
```

## Supported ORAS Dependencies

The `oras.birb.homes` registry provides internal modules for:

### Common Types Library
```yaml
deps:
  - oras.birb.homes/common/types:v1.2.0
  - oras.birb.homes/common/errors:v1.1.0
  - oras.birb.homes/common/pagination:v1.0.0
```

### Team-Specific Modules
```yaml
deps:
  - oras.birb.homes/team-platform/auth:v2.1.0
  - oras.birb.homes/team-data/schemas:v1.5.0
  - oras.birb.homes/team-api/gateway:v3.0.0
```

### Infrastructure Modules
```yaml
deps:
  - oras.birb.homes/infra/monitoring:v1.3.0
  - oras.birb.homes/infra/logging:v2.0.0
  - oras.birb.homes/infra/tracing:v1.4.0
```

## Configuration Patterns

### Basic ORAS Configuration
```yaml
# buf.yaml
version: v1
name: oras.birb.homes/my-team/my-service
deps:
  - oras.birb.homes/common/types:v1.2.0
  - buf.build/googleapis/googleapis  # Mix with public BSR
```

### Team Namespace Convention
```yaml
# Team-specific naming pattern
name: oras.birb.homes/team-{name}/{service}
deps:
  - oras.birb.homes/shared/common-types
  - oras.birb.homes/team-platform/auth
```

### Version Pinning Strategy
```yaml
# Production configuration with pinned versions
deps:
  - oras.birb.homes/common/types:v1.2.0      # Pinned major.minor.patch
  - oras.birb.homes/team-api/gateway:v3.0    # Pinned major.minor
  - oras.birb.homes/infra/monitoring:latest  # Development only
```

## Performance Optimization

### ORAS Cache Configuration
```python
# tools/oras_config.py
ORAS_CACHE_CONFIG = {
    "cache_dir": "/tmp/oras-cache",
    "max_cache_size": "10GB",
    "cache_ttl": "7d",
    "parallel_downloads": 8,
    "content_deduplication": True,
}
```

### Parallel Dependency Resolution
```starlark
# BUCK file optimization
proto_library(
    name = "optimized_service_proto",
    srcs = ["service.proto"],
    oras_deps = [
        "oras.birb.homes/common/types:v1.2.0",
        "oras.birb.homes/team-api/gateway:v3.0.0",
        "oras.birb.homes/infra/monitoring:v1.3.0",
    ],
    # All dependencies resolved in parallel
    oras_parallel_resolution = True,
    visibility = ["PUBLIC"],
)
```

### Team Cache Sharing
```bash
# Shared team cache configuration
export ORAS_CACHE_SHARED=true
export ORAS_CACHE_DIR=/shared/oras-cache
export ORAS_TEAM_ID=my-team
```

## Authentication Patterns

### Token-Based Authentication
```bash
# Environment setup
export ORAS_REGISTRY_TOKEN="your-token-here"
export ORAS_REGISTRY_URL="oras.birb.homes"
```

### Service Account Authentication
```yaml
# .oras/config.yaml
registries:
  oras.birb.homes:
    auth:
      type: service_account
      credentials_file: /path/to/service-account.json
```

### Team-Based Access Control
```yaml
# Access control example
access_policies:
  team-platform:
    read: ["team-platform", "team-api", "team-data"]
    write: ["team-platform"]
  team-api:
    read: ["team-api", "shared"]
    write: ["team-api"]
```

## Integration with CI/CD

### GitHub Actions Integration
```yaml
# .github/workflows/buf-validation.yml
- name: Setup ORAS authentication
  env:
    ORAS_REGISTRY_TOKEN: ${{ secrets.ORAS_TOKEN }}
  run: |
    echo "Authenticating with oras.birb.homes"
    
- name: Build with ORAS dependencies
  run: |
    buck2 build //...
```

### GitLab CI Integration
```yaml
# .gitlab-ci.yml
variables:
  ORAS_REGISTRY_URL: "oras.birb.homes"
  ORAS_CACHE_DIR: "/cache/oras"

before_script:
  - echo $ORAS_REGISTRY_TOKEN | oras login oras.birb.homes --username $ORAS_USERNAME --password-stdin
```

### Jenkins Pipeline
```groovy
// Jenkinsfile
pipeline {
    environment {
        ORAS_REGISTRY_TOKEN = credentials('oras-token')
        ORAS_CACHE_DIR = "/tmp/oras-cache"
    }
    stages {
        stage('Build') {
            steps {
                sh 'buck2 build //...'
            }
        }
    }
}
```

## Monitoring and Metrics

### Performance Tracking
```python
# tools/oras_metrics.py
def track_oras_performance():
    metrics = {
        "cache_hit_rate": get_cache_hit_rate(),
        "avg_resolution_time": get_avg_resolution_time(),
        "bandwidth_saved": get_bandwidth_savings(),
        "parallel_efficiency": get_parallel_efficiency(),
    }
    return metrics
```

### Build Analytics
```bash
# Performance analysis commands
python3 tools/oras_metrics.py --analyze-cache-performance
python3 tools/oras_metrics.py --dependency-resolution-time
python3 tools/oras_metrics.py --bandwidth-usage-report
```

## Troubleshooting

### Common Issues

**Authentication Failures:**
```bash
# Check authentication status
oras auth status oras.birb.homes

# Re-authenticate
echo $ORAS_TOKEN | oras login oras.birb.homes --username $USER --password-stdin
```

**Cache Issues:**
```bash
# Clear ORAS cache
python3 tools/oras_bsr.py clear-cache --registry=oras.birb.homes

# Rebuild cache
buck2 clean && buck2 build //...
```

**Network Connectivity:**
```bash
# Test registry connectivity
curl -I https://oras.birb.homes/v2/

# Check DNS resolution
nslookup oras.birb.homes
```

### Performance Debugging
```bash
# Enable verbose ORAS logging
export ORAS_DEBUG=true
export ORAS_TRACE=true

# Run with performance profiling
buck2 build //... --profile
```

## Best Practices

### 1. Namespace Organization
```
oras.birb.homes/
├── common/              # Shared utilities
├── team-{name}/         # Team-specific modules
├── infra/              # Infrastructure modules
└── experimental/       # Development modules
```

### 2. Version Management
- Use semantic versioning (v1.2.3)
- Pin versions in production
- Use version ranges for development
- Regular dependency updates

### 3. Cache Optimization
- Shared team cache directories
- Regular cache cleanup policies
- Monitor cache hit rates
- Optimize parallel resolution

### 4. Security Practices
- Regular token rotation
- Principle of least privilege
- Audit dependency usage
- Monitor access patterns

## Next Steps

After mastering ORAS registry integration:

1. **[Advanced Features](../advanced-features/)** - Custom plugins and optimization
2. **[CI/CD Patterns](../ci-cd-patterns/)** - Production deployment workflows
3. **[Multi-Service Architecture](../multi-service/)** - Complex service dependencies
4. **[Performance Tuning](../performance/)** - Large-scale optimization

---

**Leverage ORAS registries for secure, performant, enterprise-grade protobuf development! 🚀**
