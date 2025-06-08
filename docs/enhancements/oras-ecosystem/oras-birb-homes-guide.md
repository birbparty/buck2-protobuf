# 🌐 oras.birb.homes Registry Guide

**Complete guide to working with the oras.birb.homes test registry for ORAS-powered protobuf development**

## 🎯 Overview

`oras.birb.homes` is a public ORAS registry specifically designed for buck2-protobuf documentation, examples, and testing. It provides a production-like environment for learning ORAS patterns and testing your integration.

### Registry Purpose
- **Documentation Examples**: All guides reference live, working examples
- **Testing Environment**: Safe space to experiment with ORAS workflows
- **Performance Benchmarking**: Real-world performance testing
- **Integration Validation**: Verify your setup works correctly

## 🚀 Quick Start

### Registry Access
```bash
# Registry is publicly accessible for reading
Registry: oras.birb.homes
Protocol: HTTPS
Authentication: None required for pulling
Rate Limit: 1000 requests/hour per IP
```

### Basic Configuration
```bash
# Add to your .buckconfig
cat >> .buckconfig << 'EOF'

[oras]
default_registry = "oras.birb.homes"
cache_enabled = true
team_cache = true

[protobuf]
enhanced_features = true
auto_tool_management = true
EOF
```

### Verify Connection
```bash
# Test registry connectivity
buck2 run @protobuf//tools:verify_oras_setup
# ✅ Registry connection: OK
# ✅ Authentication: OK
# ✅ Cache configuration: OK

# List available examples
buck2 run @protobuf//tools:oras_list -- oras.birb.homes/examples
# Should show available example artifacts
```

## 📁 Registry Organization

### Namespace Structure
```
oras.birb.homes/
├── examples/                    # Documentation examples (PUBLIC READ)
│   ├── quickstart/              # Quick start tutorial artifacts
│   │   ├── user-api:v1.0.0     # Basic user management API
│   │   ├── order-api:v1.0.0    # Order management API
│   │   └── shared-types:v1.0.0 # Common types library
│   ├── team-collaboration/      # Team workflow examples
│   │   ├── auth-api:v1.0.0     # Authentication API
│   │   ├── payment-api:v2.0.0  # Payment processing API
│   │   └── notification-api:v1.1.0 # Notification system
│   ├── governance/              # Schema governance examples
│   │   ├── public-api:v1.0.0   # Public API with strict policies
│   │   └── internal-api:v1.0.0 # Internal API with relaxed policies
│   └── performance/             # Performance testing artifacts
│       ├── large-schema:v1.0.0 # Complex schema for performance testing
│       └── multi-lang:v1.0.0   # Multi-language generation testing
├── templates/                   # Reusable templates (PUBLIC READ)
│   ├── basic-api/               # Basic API templates
│   │   ├── grpc-service:latest # Standard gRPC service template
│   │   └── rest-api:latest     # REST API template
│   ├── microservice/            # Microservice templates
│   │   ├── event-driven:latest # Event-driven architecture
│   │   └── crud-service:latest # CRUD service template
│   └── enterprise/              # Enterprise patterns
│       ├── multi-tenant:latest # Multi-tenant API design
│       └── audit-trail:latest  # Audit trail integration
└── benchmarks/                  # Performance benchmarks (PUBLIC READ)
    ├── build-performance/       # Build time measurements
    │   ├── baseline:latest     # Performance baseline
    │   └── optimized:latest    # Optimized configuration
    ├── cache-effectiveness/     # Cache performance data
    │   └── team-data:latest    # Team caching metrics
    └── team-productivity/       # Productivity measurements
        └── metrics:latest      # Team productivity data
```

### Access Permissions
- **Public Read**: All namespaces under `examples/`, `templates/`, `benchmarks/`
- **Private Write**: Examples are maintained by the buck2-protobuf team
- **Testing**: Use your own namespace for testing: `oras.birb.homes/testing/your-username/`

## 📚 Working with Examples

### Quick Start Examples

#### User API Example
```bash
# Use the quickstart user API
load("@protobuf//rules:oras.bzl", "oras_dependency")

oras_dependency(
    name = "user_api",
    registry = "oras.birb.homes/examples/quickstart",
    artifact = "user-api",
    version = "v1.0.0",
)
```

The user API includes:
- Complete user management operations
- Input validation with protovalidate
- Go and TypeScript generation ready
- gRPC and Connect framework support

#### Multi-Service Architecture
```bash
# Complete e-commerce example
oras_dependency(
    name = "user_api",
    registry = "oras.birb.homes/examples/quickstart", 
    artifact = "user-api",
    version = "v1.0.0",
)

oras_dependency(
    name = "order_api",
    registry = "oras.birb.homes/examples/quickstart",
    artifact = "order-api", 
    version = "v1.0.0",
)

oras_dependency(
    name = "shared_types",
    registry = "oras.birb.homes/examples/quickstart",
    artifact = "shared-types",
    version = "v1.0.0",
)
```

### Team Collaboration Examples

#### Authentication Integration
```bash
# Production-ready authentication API
oras_dependency(
    name = "auth_api",
    registry = "oras.birb.homes/examples/team-collaboration",
    artifact = "auth-api",
    version = "v1.0.0",
)
```

Features included:
- JWT token management
- Role-based access control
- Multi-factor authentication support
- Session management

#### Payment Processing
```bash
# Secure payment API with validation
oras_dependency(
    name = "payment_api", 
    registry = "oras.birb.homes/examples/team-collaboration",
    artifact = "payment-api",
    version = "v2.0.0",
)
```

Features included:
- PCI DSS compliant design
- Multiple payment methods
- Webhook integration
- Fraud detection hooks

### Governance Examples

#### Public API Design
```bash
# API with strict governance policies
oras_dependency(
    name = "public_api",
    registry = "oras.birb.homes/examples/governance",
    artifact = "public-api",
    version = "v1.0.0",
)
```

Demonstrates:
- Comprehensive field validation
- Backward compatibility requirements
- Documentation standards
- Deprecation patterns

## 🛠️ Testing Your Own APIs

### Using Testing Namespace
```bash
# Publish to your testing namespace
oras_publish(
    name = "my_test_api",
    proto = ":my_proto",
    registry = "oras.birb.homes/testing/your-username",
    version = "v0.1.0",
    description = "Testing my API integration",
)
```

### Testing Workflow
1. **Develop locally** with Buck2 + ORAS rules
2. **Publish to testing namespace** for validation
3. **Test consumption** from different clients
4. **Measure performance** with real registry
5. **Validate caching** with team scenarios

### Testing Examples
```bash
# Test publishing
buck2 run //my-api:my_test_api
# 🚀 Published to oras.birb.homes/testing/your-username/my-api:v0.1.0

# Test consumption
oras_dependency(
    name = "my_test_dep",
    registry = "oras.birb.homes/testing/your-username", 
    artifact = "my-api",
    version = "v0.1.0",
)

buck2 build //client:test_client
# ⚡ Downloaded and integrated successfully
```

## 📊 Performance Benchmarking

### Available Benchmarks

#### Build Performance Baseline
```bash
# Use performance baseline for comparison
oras_dependency(
    name = "perf_baseline",
    registry = "oras.birb.homes/benchmarks/build-performance",
    artifact = "baseline",
    version = "latest",
)

# Run performance comparison
buck2 build :perf_baseline --profile
# Compare your build times against baseline
```

#### Cache Effectiveness Testing
```bash
# Test team caching scenarios
oras_dependency(
    name = "cache_test",
    registry = "oras.birb.homes/benchmarks/cache-effectiveness",
    artifact = "team-data",
    version = "latest",
)

# Measure cache hit rates
buck2 run @protobuf//tools:cache_stats
# Should show >90% cache hits for repeated builds
```

### Performance Targets
| Metric | Target | Description |
|--------|--------|-------------|
| First download | <2s | Initial artifact download |
| Cached build | <0.5s | Subsequent builds with cache |
| Team cache hit | >90% | Cache effectiveness across team |
| Registry latency | <100ms | Network latency to registry |

## 🔧 Advanced Usage

### Multi-Registry Setup
```bash
# Use oras.birb.homes alongside other registries
[oras]
default_registry = "oras.birb.homes"
registries = [
    "oras.birb.homes",
    "your-company.registry.com",
    "ghcr.io/your-org",
]
```

### Custom Caching Configuration
```bash
# Optimize caching for oras.birb.homes
[oras.cache]
enabled = true
max_size = "10GB"
ttl = "24h"
registry_specific = {
    "oras.birb.homes" = {
        "ttl" = "7d",  # Examples don't change often
        "aggressive" = true,
    }
}
```

### Registry Mirroring
```bash
# Mirror critical examples locally
buck2 run @protobuf//tools:oras_mirror -- \
    --source="oras.birb.homes/examples/quickstart" \
    --dest="your-local-registry/examples/quickstart"
```

## 🛠️ Troubleshooting

### Common Issues

#### "Registry not accessible"
```bash
# Check network connectivity
curl -I https://oras.birb.homes/v2/
# Should return HTTP/2 200

# Check DNS resolution
nslookup oras.birb.homes
# Should resolve to valid IP
```

#### "Artifact not found"
```bash
# List available artifacts
buck2 run @protobuf//tools:oras_list -- oras.birb.homes/examples

# Check specific namespace
buck2 run @protobuf//tools:oras_list -- oras.birb.homes/examples/quickstart

# Verify artifact name and version
buck2 run @protobuf//tools:oras_inspect -- \
    oras.birb.homes/examples/quickstart/user-api:v1.0.0
```

#### "Download timeout"
```bash
# Check download speed
buck2 run @protobuf//tools:oras_test_download -- \
    oras.birb.homes/examples/quickstart/user-api:v1.0.0
    
# Use parallel downloads
[oras]
parallel_downloads = 8
download_timeout = "30s"
```

#### "Cache issues"
```bash
# Clear ORAS cache
buck2 run @protobuf//tools:oras_cache_clear

# Verify cache configuration
buck2 run @protobuf//tools:oras_cache_info
# Should show cache location and size
```

### Performance Issues

#### Slow Downloads
```bash
# Enable download acceleration
[oras]
compression_enabled = true
parallel_downloads = 8
cdn_enabled = true
```

#### Cache Misses
```bash
# Check cache configuration
buck2 config show oras.cache_enabled
# Should be true

# Monitor cache statistics
buck2 run @protobuf//tools:cache_monitor
# Shows real-time cache hit/miss rates
```

## 📈 Monitoring & Analytics

### Registry Health
```bash
# Check registry status
buck2 run @protobuf//tools:oras_health -- oras.birb.homes
# ✅ Registry: Healthy
# ✅ Latency: 85ms
# ✅ Throughput: Normal
```

### Usage Analytics
```bash
# View your usage statistics
buck2 run @protobuf//tools:oras_stats -- oras.birb.homes
# Downloads: 1,234
# Cache hits: 987 (80%)
# Bandwidth saved: 2.3GB
```

### Performance Monitoring
```bash
# Monitor build performance
buck2 run @protobuf//tools:performance_monitor
# Track: Download times, cache effectiveness, build duration
```

## 🌟 Best Practices

### Dependency Management
```bash
# Pin versions for stability
oras_dependency(
    name = "stable_api",
    registry = "oras.birb.homes/examples/quickstart",
    artifact = "user-api",
    version = "v1.0.0",  # Specific version, not "latest"
)

# Use version ranges for testing
oras_dependency(
    name = "test_api",
    registry = "oras.birb.homes/testing/your-username",
    artifact = "my-api",
    version = "v0.*",  # Allow patch updates
)
```

### Performance Optimization
```bash
# Pre-warm cache for team
buck2 run @protobuf//tools:oras_prewarm -- \
    oras.birb.homes/examples/quickstart/user-api:v1.0.0 \
    oras.birb.homes/examples/quickstart/order-api:v1.0.0
    
# Use build profiles for optimization
buck2 build //... --profile=oras-optimized
```

### Testing Strategy
```bash
# Test with multiple registry configurations
buck2 test //... --config=oras-registry-only
buck2 test //... --config=multi-registry
buck2 test //... --config=offline-cache
```

## 🚀 Advanced Patterns

### Template-Based Development
```bash
# Start from proven templates
oras_dependency(
    name = "service_template",
    registry = "oras.birb.homes/templates/microservice",
    artifact = "event-driven",
    version = "latest",
)

# Customize for your needs
proto_library(
    name = "my_service",
    srcs = ["my_service.proto"],
    template = ":service_template",
    customizations = {
        "package": "mycompany.myservice.v1",
        "go_package": "github.com/mycompany/myservice/v1",
    },
)
```

### CI/CD Integration
```bash
# Use in GitHub Actions
- name: Test with oras.birb.homes
  run: |
    buck2 build //... --registry=oras.birb.homes
    buck2 test //... --config=oras-integration
```

### Local Development
```bash
# Hybrid local/registry development
[oras]
local_override = {
    "oras.birb.homes/testing/my-username/*" = "file://./local-dev/",
}
```

## 📚 Example Collections

### Quick Start Collection
Perfect for learning ORAS fundamentals:
- `user-api:v1.0.0` - Basic CRUD operations
- `order-api:v1.0.0` - Business logic patterns  
- `shared-types:v1.0.0` - Common type libraries

### Team Collaboration Collection
Demonstrates team workflows:
- `auth-api:v1.0.0` - Authentication & authorization
- `payment-api:v2.0.0` - Secure payment processing
- `notification-api:v1.1.0` - Event-driven notifications

### Enterprise Collection
Production-ready patterns:
- `public-api:v1.0.0` - Public API design
- `internal-api:v1.0.0` - Internal service patterns
- `audit-trail:latest` - Compliance and auditing

---

**🌐 oras.birb.homes provides the perfect environment for learning and testing ORAS-powered protobuf development.** 

*All examples are production-ready and demonstrate real-world patterns you can adopt in your own projects.*

*Next: [Explore distribution patterns →](distribution-patterns.md)*
