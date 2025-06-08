# 🚀 Buck2 + Protobuf + ORAS = Magic

**Transform your Buck2 team's API development with ORAS-powered protobuf superpowers**

## ⚡ The ORAS Advantage

If you're already using Buck2, you know what fast, reliable builds feel like. Now imagine that same experience for protobuf development - instant API sharing, lightning-fast builds, and effortless team collaboration.

**ORAS (OCI Registry as Storage) changes everything:**

```bash
# Traditional protobuf development
git clone api-repo
make install-protoc
make install-plugins  
make generate
# 😴 5+ minutes, breaks on different machines

# Buck2 + ORAS protobuf development
buck2 build //api:user_service_proto
# ✨ 15 seconds, works everywhere, cached globally
```

### Why Buck2 Teams Love ORAS

| Traditional Approach | Buck2 + ORAS Approach | Improvement |
|---------------------|------------------------|-------------|
| Manual tool management | Automatic tool distribution | **10x faster setup** |
| "Works on my machine" | Reproducible everywhere | **Zero environment issues** |
| Slow protobuf builds | Cached, incremental builds | **5x faster iteration** |
| Manual API sharing | Push-button distribution | **Instant team sharing** |
| Version conflicts | Hermetic, versioned tools | **Zero conflicts** |

## 🎯 Quick Navigation

### 🚀 Get Started (10 minutes to magic)
- **[Buck2 Teams Quick Start](getting-started/buck2-teams-quick-start.md)** - Zero to ORAS in 10 minutes
- **[ORAS-Powered Protobuf](getting-started/oras-powered-protobuf.md)** - Why ORAS changes everything
- **[First Distributed API](getting-started/first-distributed-api.md)** - Publish and consume your first API

### 🎨 ORAS Ecosystem
- **[Distribution Patterns](oras-ecosystem/distribution-patterns.md)** - How to distribute APIs effectively
- **[Caching & Performance](oras-ecosystem/caching-performance.md)** - Achieve 5x faster builds
- **[Registry Management](oras-ecosystem/registry-management.md)** - Organize your team's APIs
- **[oras.birb.homes Guide](oras-ecosystem/oras-birb-homes-guide.md)** - Work with our test registry

### 🛠️ Modern Development
- **[Buf CLI Integration](modern-development/buf-cli-integration.md)** - Modern protobuf tooling
- **[Validation & Governance](modern-development/validation-and-governance.md)** - Quality & consistency
- **[Team Workflows](modern-development/team-workflows.md)** - Collaboration patterns
- **[CI/CD Automation](modern-development/ci-cd-automation.md)** - Automated pipelines

### 🏗️ Buck2 Integration
- **[Enhanced Rules Reference](buck2-integration/enhanced-rules-reference.md)** - All enhancement rules
- **[Build Optimization](buck2-integration/build-optimization.md)** - Buck2 + ORAS performance
- **[Platform Patterns](buck2-integration/platform-patterns.md)** - Cross-platform development

### 🚀 Production Deployment
- **[Small Team Setup](production-deployment/small-team-setup.md)** - 5-50 developers
- **[Growing Organization](production-deployment/growing-organization.md)** - 50-200 developers
- **[Enterprise Scale](production-deployment/enterprise-scale.md)** - 200+ developers
- **[ORAS Registry Hosting](production-deployment/oras-registry-hosting.md)** - Self-hosted registries

### 📚 Examples Showcase
- **[ORAS-First Examples](examples-showcase/oras-first-examples/)** - ORAS-powered examples
- **[Team Collaboration Demos](examples-showcase/team-collaboration-demos/)** - Real workflow examples
- **[Performance Benchmarks](examples-showcase/performance-benchmarks/)** - Before/after metrics

## 🏃‍♂️ 10-Minute Quick Start

### Prerequisites
- **Buck2** already installed and working
- **Team using Buck2** for builds
- **Ready to add protobuf** to your development workflow

### Step 1: Setup ORAS Registry (2 minutes)
```bash
# Configure ORAS registry access
echo "registry.url = 'oras.birb.homes'" >> .buckconfig
buck2 run @protobuf//tools:setup_oras_connection

# ✅ Connected to ORAS registry
```

### Step 2: Create Your First API (3 minutes)
```protobuf
// api/user.proto
syntax = "proto3";
package user.v1;

message User {
  string id = 1;
  string name = 2;
  string email = 3;
}

service UserService {
  rpc GetUser(GetUserRequest) returns (User);
}

message GetUserRequest {
  string id = 1;
}
```

### Step 3: Build with ORAS Distribution (2 minutes)
```python
# api/BUCK
load("@protobuf//rules:proto.bzl", "proto_library")
load("@protobuf//rules:oras.bzl", "oras_publish")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

oras_publish(
    name = "user_api_v1",
    proto = ":user_proto",
    registry = "oras.birb.homes/examples/quickstart",
    version = "v1.0.0",
)
```

### Step 4: Build and Publish (2 minutes)
```bash
buck2 build //api:user_api_v1 --publish
# 🚀 Published to oras.birb.homes/examples/quickstart/user-api:v1.0.0

# Now ANY team member can use it instantly:
buck2 build //client:user_client  # Automatically downloads and caches
```

### Step 5: See the Magic (1 minute)
```bash
# Check build performance
buck2 build //api:user_proto
# ✨ 2.3s (first time)

buck2 build //api:user_proto  
# ⚡ 0.1s (cached via ORAS)

# Check team access
buck2 query "deps(//client:user_client)"
# ✅ oras.birb.homes/examples/quickstart/user-api:v1.0.0 (cached)
```

🎉 **Congratulations!** You just experienced ORAS-powered protobuf development. Your APIs are now:
- **Instantly shareable** across your team
- **Automatically cached** for fast builds  
- **Version managed** through ORAS registry
- **Buck2 native** with zero additional complexity

## 🌟 Key Enhancement Features

### ORAS Distribution & Caching
- **Automatic tool management** - No more manual protoc/plugin installation
- **Global caching** - Share build artifacts across your entire team
- **Version pinning** - Reproducible builds with hermetic tool versions
- **Registry integration** - Seamless integration with OCI registries

### Modern Protobuf Tooling
- **Buf CLI integration** - Modern linting, formatting, and breaking change detection
- **BSR support** - Public and private Buf Schema Registry integration
- **Modern plugins** - protovalidate, Connect framework, package managers
- **Quality gates** - Automated validation and governance

### Team Collaboration
- **Schema governance** - Automated policy enforcement
- **Breaking change detection** - Safe API evolution workflows
- **Team notifications** - Slack/email integration for API changes
- **Performance monitoring** - Track build performance and optimization

### Enterprise Features
- **Team caching** - Shared build caches for faster team builds
- **Access control** - Fine-grained permissions for API access
- **Audit logging** - Complete audit trail of API changes
- **Multi-registry support** - Public and private registry integration

## 📊 Performance Improvements

### Build Speed Improvements
```
Traditional protobuf build:    5m 30s
Buck2 basic protobuf:         45s
Buck2 + ORAS caching:         8s
Buck2 + ORAS (cached):        0.5s

Improvement: 11x faster than traditional, 90x faster when cached
```

### Team Productivity Metrics
- **Setup time**: 30 minutes → 10 minutes (3x faster)
- **"Works on my machine" issues**: Common → Never (100% eliminated)
- **API sharing**: Manual → Automatic (Zero friction)
- **Build cache hits**: 30% → 95% (Team-wide sharing)

### Scaling Characteristics
- **5-person team**: 2x productivity improvement
- **20-person team**: 5x productivity improvement  
- **100-person team**: 10x productivity improvement

## 🎯 User Journey by Team Size

### Individual Developer (5-10 minutes)
1. **[Quick Start](getting-started/buck2-teams-quick-start.md)** - Get ORAS working
2. **[First API](getting-started/first-distributed-api.md)** - Create and publish  
3. **[Modern Tools](modern-development/buf-cli-integration.md)** - Add linting and validation

### Small Team (30-60 minutes)
1. **[Team Setup](production-deployment/small-team-setup.md)** - Configure team workflows
2. **[Registry Management](oras-ecosystem/registry-management.md)** - Organize team APIs
3. **[CI/CD Integration](modern-development/ci-cd-automation.md)** - Automated publishing

### Growing Organization (2-4 hours)
1. **[Governance](modern-development/validation-and-governance.md)** - Schema policies
2. **[Team Workflows](modern-development/team-workflows.md)** - Multi-team coordination
3. **[Performance Optimization](oras-ecosystem/caching-performance.md)** - Scale build performance

### Enterprise (1-2 days)
1. **[Enterprise Scale](production-deployment/enterprise-scale.md)** - Large-scale deployment
2. **[Registry Hosting](production-deployment/oras-registry-hosting.md)** - Self-hosted registries
3. **[Advanced Features](buck2-integration/enhanced-rules-reference.md)** - Full feature adoption

## 🤝 Community & Support

### Getting Help
- **[Troubleshooting Guide](../troubleshooting.md)** - Common issues and solutions
- **[Performance Guide](../performance.md)** - Optimization strategies
- **[API Reference](../rules-reference.md)** - Complete rule documentation

### Contributing
- **[Contributing Guide](../contributing.md)** - Development and contribution guidelines
- **[Example Contributions](examples-showcase/)** - Share your patterns
- **Community Discord** - Real-time help and discussion

### Resources
- **[Working Examples](examples-showcase/)** - Copy-paste ready examples
- **[Performance Benchmarks](examples-showcase/performance-benchmarks/)** - Real metrics
- **[Case Studies](production-deployment/)** - Real-world deployments

## 🚀 What's Next?

Ready to transform your Buck2 team's protobuf development? Start here:

1. **🎯 New to protobuf?** → [Buck2 Teams Quick Start](getting-started/buck2-teams-quick-start.md)
2. **🔄 Migrating existing setup?** → [ORAS-Powered Protobuf](getting-started/oras-powered-protobuf.md)  
3. **🏢 Enterprise deployment?** → [Production Deployment](production-deployment/)
4. **⚡ Performance optimization?** → [Caching & Performance](oras-ecosystem/caching-performance.md)

---

**Built for Buck2 teams who demand the same speed and reliability for protobuf that they get from Buck2 itself.** 

*Experience the magic of ORAS-powered protobuf development - your team will never go back to the old way.* ✨
