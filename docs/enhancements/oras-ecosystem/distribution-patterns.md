# 📦 API Distribution Patterns with ORAS

**Proven patterns for organizing, versioning, and distributing protobuf APIs at scale**

## 🎯 Overview

Effective API distribution is critical for team productivity and system reliability. ORAS enables powerful distribution patterns that scale from individual projects to enterprise architectures.

This guide covers proven patterns used by successful teams to organize, version, and distribute their protobuf APIs using ORAS registries.

## 🏗️ Core Distribution Patterns

### 1. Namespace Organization

#### Team-Based Namespaces
```
your-registry.com/
├── platform-team/
│   ├── auth-api:v1.0.0
│   ├── common-types:v2.1.0
│   └── core-services:v1.5.0
├── user-team/
│   ├── user-api:v2.0.0
│   ├── profile-api:v1.3.0
│   └── preferences-api:v1.0.0
├── commerce-team/
│   ├── order-api:v1.8.0
│   ├── payment-api:v2.2.0
│   └── inventory-api:v1.4.0
└── shared/
    ├── common-proto:v3.0.0
    ├── error-types:v1.0.0
    └── pagination:v2.0.0
```

**Buck2 Configuration:**
```python
# Team-specific API publishing
oras_publish(
    name = "user_api_publish",
    proto = ":user_proto",
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    labels = {
        "team": "user-team",
        "category": "user-management",
        "stability": "stable",
    },
)
```

#### Domain-Based Namespaces
```
your-registry.com/
├── authentication/
│   ├── oauth-api:v2.0.0
│   ├── session-api:v1.5.0
│   └── rbac-api:v1.0.0
├── commerce/
│   ├── catalog-api:v1.2.0
│   ├── pricing-api:v2.0.0
│   └── promotion-api:v1.0.0
├── communication/
│   ├── email-api:v1.3.0
│   ├── sms-api:v1.1.0
│   └── notification-api:v2.0.0
└── infrastructure/
    ├── logging-api:v1.0.0
    ├── metrics-api:v2.1.0
    └── tracing-api:v1.0.0
```

### 2. Version Management Patterns

#### Semantic Versioning Strategy
```python
# Major version (breaking changes)
oras_publish(
    name = "user_api_v2",
    proto = ":user_proto_v2",
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    description = "User API v2 - Complete redesign",
    breaking_change = True,
    migration_guide = "//docs:user-api-v1-to-v2-migration.md",
)

# Minor version (new features, backward compatible)
oras_publish(
    name = "user_api_v2_1",
    proto = ":user_proto_v2_1",
    registry = "your-registry.com/user-team", 
    version = "v2.1.0",
    description = "Added user preferences endpoint",
    changelog = "//docs:user-api-v2.1.0-changelog.md",
)

# Patch version (bug fixes)
oras_publish(
    name = "user_api_v2_1_1",
    proto = ":user_proto_v2_1_1",
    registry = "your-registry.com/user-team",
    version = "v2.1.1", 
    description = "Fixed validation rules for email field",
)
```

#### Parallel Version Support
```python
# Support multiple major versions simultaneously
oras_publish(
    name = "user_api_v1_latest",
    proto = ":user_proto_v1",
    registry = "your-registry.com/user-team",
    version = "v1.15.3",  # Latest v1.x
    support_status = "maintenance",
    eol_date = "2024-12-31",
)

oras_publish(
    name = "user_api_v2_latest", 
    proto = ":user_proto_v2",
    registry = "your-registry.com/user-team",
    version = "v2.5.0",   # Latest v2.x
    support_status = "active",
)

oras_publish(
    name = "user_api_v3_beta",
    proto = ":user_proto_v3",
    registry = "your-registry.com/user-team",
    version = "v3.0.0-beta.2",
    support_status = "preview",
    stability = "experimental",
)
```

### 3. Dependency Management Patterns

#### Layered Dependencies
```python
# Foundation layer - stable, rarely changing
oras_dependency(
    name = "foundation_types",
    registry = "your-registry.com/shared",
    artifact = "common-proto",
    version = "v3.0.0",
    stability = "stable",
)

# Platform layer - core services
oras_dependency(
    name = "auth_api",
    registry = "your-registry.com/platform-team",
    artifact = "auth-api", 
    version = "v1.0.0",
    deps = [":foundation_types"],
)

# Application layer - business logic
oras_dependency(
    name = "user_api",
    registry = "your-registry.com/user-team",
    artifact = "user-api",
    version = "v2.0.0",
    deps = [":foundation_types", ":auth_api"],
)
```

#### Version Pinning Strategies
```python
# Production: Pin exact versions
oras_dependency(
    name = "prod_user_api",
    registry = "your-registry.com/user-team",
    artifact = "user-api",
    version = "v2.1.3",  # Exact version
    environment = "production",
)

# Staging: Allow patch updates
oras_dependency(
    name = "staging_user_api", 
    registry = "your-registry.com/user-team",
    artifact = "user-api",
    version = "v2.1.*",  # Latest patch
    environment = "staging",
)

# Development: Allow minor updates
oras_dependency(
    name = "dev_user_api",
    registry = "your-registry.com/user-team", 
    artifact = "user-api",
    version = "v2.*",    # Latest minor
    environment = "development",
)
```

## 🎨 Advanced Distribution Patterns

### 1. Multi-Registry Federation

#### Public/Private Registry Strategy
```python
# Public dependencies from BSR
oras_dependency(
    name = "google_apis",
    registry = "buf.build/googleapis/googleapis",
    artifact = "google-cloud-common",
    version = "v1.0.0",
)

# Private dependencies from corporate registry
oras_dependency(
    name = "internal_apis",
    registry = "artifacts.company.com/apis",
    artifact = "internal-common",
    version = "v2.0.0",
)

# Local team registry
oras_dependency(
    name = "team_apis",
    registry = "oras.birb.homes/your-team",
    artifact = "team-specific-api",
    version = "v1.0.0",
)
```

#### Registry Fallback Chain
```bash
# .buckconfig registry configuration
[oras]
registries = [
    "artifacts.company.com",     # Primary corporate registry
    "oras.birb.homes",          # Secondary public registry
    "buf.build",                # BSR fallback
]

fallback_strategy = "cascade"  # Try registries in order
cache_cross_registry = true    # Cache across registries
```

### 2. Staging and Promotion Patterns

#### Environment Promotion Pipeline
```python
# Development environment
oras_publish(
    name = "dev_release",
    proto = ":user_proto",
    registry = "dev-registry.company.com/user-team",
    version = "v2.1.0-dev.${BUILD_NUMBER}",
    environment = "development",
)

# Staging promotion
oras_promote(
    name = "stage_promotion",
    source = "dev-registry.company.com/user-team/user-api:v2.1.0-dev.123",
    dest = "stage-registry.company.com/user-team/user-api:v2.1.0-stage.1",
    tests = ["//tests:integration_tests"],
)

# Production promotion
oras_promote(
    name = "prod_promotion", 
    source = "stage-registry.company.com/user-team/user-api:v2.1.0-stage.1",
    dest = "prod-registry.company.com/user-team/user-api:v2.1.0",
    approval_required = True,
    tests = ["//tests:production_readiness_tests"],
)
```

#### Feature Branch Distribution
```python
# Feature branch publishing
oras_publish(
    name = "feature_api",
    proto = ":user_proto",
    registry = "dev-registry.company.com/user-team",
    version = "v2.1.0-feature-${BRANCH_NAME}-${BUILD_NUMBER}",
    ttl = "7d",  # Auto-cleanup after 7 days
    labels = {
        "branch": "${BRANCH_NAME}",
        "pr": "${PR_NUMBER}",
        "experimental": "true",
    },
)
```

### 3. Microservice Distribution Patterns

#### Service Mesh Integration
```python
# API with service mesh metadata
oras_publish(
    name = "user_service_api",
    proto = ":user_proto",
    registry = "your-registry.com/services",
    version = "v2.0.0",
    service_mesh = {
        "name": "user-service",
        "namespace": "production",
        "port": 8080,
        "protocol": "grpc",
        "health_check": "/health",
    },
    labels = {
        "service-mesh": "istio",
        "load-balancing": "round-robin",
        "circuit-breaker": "enabled",
    },
)
```

#### API Gateway Integration
```python
# API with gateway configuration
oras_publish(
    name = "public_user_api",
    proto = ":user_public_proto",
    registry = "your-registry.com/public-apis",
    version = "v1.0.0",
    api_gateway = {
        "path_prefix": "/api/v1/users",
        "rate_limit": "1000/hour",
        "auth_required": True,
        "cors_enabled": True,
    },
    openapi_spec = ":user_openapi_spec",
)
```

## 🚀 Performance Optimization Patterns

### 1. Caching Strategies

#### Aggressive Caching for Stable APIs
```python
# Stable APIs with long cache TTL
oras_publish(
    name = "stable_common_api",
    proto = ":common_proto",
    registry = "your-registry.com/shared",
    version = "v3.0.0",
    cache_policy = {
        "ttl": "30d",        # Cache for 30 days
        "immutable": True,   # Never changes once published
        "cdn_cache": True,   # Enable CDN caching
    },
)
```

#### Smart Caching for Frequent Updates
```python
# Development APIs with intelligent caching
oras_publish(
    name = "dev_api",
    proto = ":user_proto",
    registry = "dev-registry.company.com/user-team", 
    version = "v2.1.0-dev.${BUILD_NUMBER}",
    cache_policy = {
        "ttl": "1h",         # Short cache for development
        "if_unchanged": "24h", # Longer cache if content unchanged
        "team_shared": True,  # Share cache across team
    },
)
```

### 2. Parallel Distribution

#### Multi-Target Publishing
```python
# Publish to multiple registries simultaneously
oras_publish_multi(
    name = "multi_registry_publish",
    proto = ":user_proto",
    destinations = [
        {
            "registry": "primary-registry.company.com/user-team",
            "version": "v2.0.0",
            "primary": True,
        },
        {
            "registry": "backup-registry.company.com/user-team", 
            "version": "v2.0.0",
            "mirror": True,
        },
        {
            "registry": "public-registry.company.com/user-team",
            "version": "v2.0.0",
            "public": True,
            "sanitized": True,  # Remove internal fields
        },
    ],
)
```

#### Parallel Artifact Generation
```python
# Generate multiple language bindings in parallel
oras_publish_bundle(
    name = "multi_lang_api",
    proto = ":user_proto",
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    languages = {
        "go": {
            "package": "github.com/company/apis/user/v2",
            "grpc": True,
        },
        "typescript": {
            "package": "@company/user-api",
            "connect": True,
        },
        "python": {
            "package": "company.apis.user.v2",
            "grpc": True,
        },
        "rust": {
            "package": "company-user-api",
            "tonic": True,
        },
    },
    parallel = True,  # Generate all languages in parallel
)
```

## 🏢 Enterprise Distribution Patterns

### 1. Compliance and Governance

#### Audit Trail Integration
```python
# API with comprehensive audit trail
oras_publish(
    name = "audited_api",
    proto = ":sensitive_proto",
    registry = "secure-registry.company.com/finance-team",
    version = "v1.0.0",
    compliance = {
        "classification": "confidential",
        "data_residency": "US",
        "retention_policy": "7y",
        "audit_trail": True,
    },
    approvals = [
        "security-team",
        "compliance-team", 
        "api-governance-board",
    ],
)
```

#### Access Control Patterns
```python
# Role-based access control
oras_publish(
    name = "rbac_api",
    proto = ":user_proto",
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    access_control = {
        "read": ["user-team", "platform-team"],
        "write": ["user-team-leads"],
        "admin": ["api-governance"],
    },
    environments = {
        "production": {
            "read": ["user-team", "platform-team", "sre-team"],
            "write": [],  # Read-only in production
        },
        "staging": {
            "read": ["user-team", "platform-team", "qa-team"],
            "write": ["user-team"],
        },
    },
)
```

### 2. Multi-Tenant Distribution

#### Tenant-Specific APIs
```python
# Per-tenant API distribution
oras_publish_per_tenant(
    name = "tenant_specific_api",
    proto = ":user_proto",
    base_registry = "your-registry.com",
    version = "v2.0.0",
    tenants = [
        {
            "id": "enterprise-customer-1",
            "registry": "your-registry.com/tenant-enterprise-customer-1",
            "customizations": {
                "field_encryption": ["email", "phone"],
                "custom_fields": ["enterprise_id"],
            },
        },
        {
            "id": "startup-customer-2", 
            "registry": "your-registry.com/tenant-startup-customer-2",
            "customizations": {
                "rate_limits": {"create_user": "100/day"},
                "features": ["basic"],
            },
        },
    ],
)
```

## 📊 Monitoring and Analytics

### 1. Distribution Metrics

#### Usage Analytics
```python
# API with usage tracking
oras_publish(
    name = "tracked_api",
    proto = ":user_proto",
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    analytics = {
        "track_downloads": True,
        "track_usage": True,
        "track_performance": True,
        "dashboard": "grafana.company.com/api-metrics",
    },
)
```

#### Health Monitoring
```bash
# Monitor API distribution health
buck2 run @protobuf//tools:oras_health_check -- \
    --registry="your-registry.com" \
    --alert-threshold="95%" \
    --metrics-endpoint="metrics.company.com"
```

### 2. Performance Monitoring

#### Build Performance Tracking
```python
# Performance-monitored publishing
oras_publish(
    name = "perf_monitored_api",
    proto = ":user_proto", 
    registry = "your-registry.com/user-team",
    version = "v2.0.0",
    performance_monitoring = {
        "track_build_time": True,
        "track_publish_time": True,
        "track_download_time": True,
        "baseline": "oras.birb.homes/benchmarks/build-performance/baseline:latest",
    },
)
```

## 🌟 Best Practices Summary

### Distribution Organization
- **Use consistent namespacing** (team-based or domain-based)
- **Implement semantic versioning** for predictable updates
- **Organize by stability** (stable, beta, experimental)
- **Document API lifecycle** (active, maintenance, deprecated)

### Version Management
- **Pin exact versions** in production environments
- **Use version ranges** appropriately for development
- **Support parallel major versions** during transitions
- **Provide clear migration paths** for breaking changes

### Performance Optimization
- **Cache aggressively** for stable APIs
- **Use parallel publishing** for multi-language APIs
- **Implement registry federation** for reliability
- **Monitor distribution performance** continuously

### Enterprise Readiness
- **Implement audit trails** for compliance
- **Use role-based access control** for security
- **Support multi-tenant scenarios** when needed
- **Integrate with monitoring systems** for observability

---

**📦 Effective API distribution patterns scale from individual productivity to enterprise coordination.**

*Choose patterns that match your team size and complexity, then evolve as you grow.*

*Next: [Optimize caching and performance →](caching-performance.md)*
