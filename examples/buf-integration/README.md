# 🚀 Comprehensive Buf Integration Examples

This directory provides comprehensive examples demonstrating the full power of buf integration with buck2-protobuf. These examples progress from simple getting started scenarios to advanced production patterns, serving as both learning resources and integration tests.

## 📖 Learning Path

### 🎯 Getting Started
1. **[Quickstart](quickstart/)** - Simple examples to get you started
2. **[Basic Validation](quickstart/validation/)** - Linting and formatting basics
3. **[Simple Breaking Changes](quickstart/breaking/)** - Basic compatibility checking

### 🔄 API Evolution
1. **[API Evolution](api-evolution/)** - Real-world API versioning patterns
2. **[Breaking Change Workflows](api-evolution/workflows/)** - Production change management
3. **[Migration Strategies](api-evolution/migration/)** - Safe evolution practices

### 🏗️ Multi-Service Architecture
1. **[Microservices](multi-service/)** - Realistic service architecture
2. **[Shared Libraries](multi-service/shared/)** - Common types and patterns
3. **[Integration Testing](multi-service/integration/)** - End-to-end validation

### 🚀 Production Patterns
1. **[CI/CD Integration](ci-cd-patterns/)** - Automated validation workflows
2. **[ORAS Registry](oras-registry/)** - Private registry integration
3. **[Advanced Features](advanced-features/)** - Custom plugins and optimization

### 📚 Migration & Best Practices
1. **[Migration Guides](migration-guides/)** - From existing protobuf setups
2. **[Best Practices](best-practices/)** - Production-ready patterns
3. **[Troubleshooting](troubleshooting/)** - Common issues and solutions

## 🎯 Key Features Demonstrated

### ✅ Core Buf Functionality
- **Linting**: Comprehensive rule coverage and customization
- **Formatting**: Automated code formatting and CI integration
- **Breaking Changes**: Compatibility validation and safe evolution
- **Configuration Discovery**: Automatic buf.yaml and buf.work.yaml detection

### ✅ Registry Integration
- **BSR Dependencies**: Public Buf Schema Registry integration
- **ORAS Registry**: Private `oras.birb.homes` registry usage
- **Hybrid Registries**: Combining public and private dependencies
- **Performance Optimization**: Caching and parallel resolution

### ✅ Production Workflows
- **CI/CD Integration**: GitHub Actions, GitLab CI, Jenkins patterns
- **Team Collaboration**: Multi-team development workflows
- **Security Patterns**: API security best practices
- **Performance Tuning**: Large-scale optimization strategies

### ✅ Advanced Capabilities
- **Custom Plugins**: Organization-specific validation rules
- **Multi-Module Workspaces**: Complex project structures
- **Migration Tools**: Automated migration from legacy setups
- **Monitoring & Metrics**: Build performance and quality tracking

## 🏃‍♂️ Quick Start

### 1. Simple Linting Example
```bash
# Navigate to quickstart example
cd examples/buf-integration/quickstart/

# Run basic linting
buck2 run //:lint_simple

# View the results
buck2 build //:user_service_proto
```

### 2. Breaking Change Detection
```bash
# Navigate to API evolution example
cd examples/buf-integration/api-evolution/

# Check breaking changes between versions
buck2 run //:check_v1_to_v2_breaking
buck2 run //:check_v2_to_v3_breaking
```

### 3. Multi-Service Architecture
```bash
# Navigate to multi-service example
cd examples/buf-integration/multi-service/

# Build all services
buck2 build //user-service:user_service_proto
buck2 build //order-service:order_service_proto
buck2 build //shared-types:common_types_proto
```

### 4. ORAS Registry Integration
```bash
# Navigate to ORAS examples
cd examples/buf-integration/oras-registry/

# Test private registry integration
buck2 run //:test_private_deps
```

## 📊 Example Categories

### 🎯 Beginner Examples
| Example | Description | Key Features |
|---------|-------------|--------------|
| `quickstart/basic-lint/` | Simple linting setup | Basic buf_lint usage |
| `quickstart/formatting/` | Code formatting | buf_format integration |
| `quickstart/validation/` | Input validation | Error handling patterns |

### 🔄 Intermediate Examples  
| Example | Description | Key Features |
|---------|-------------|--------------|
| `api-evolution/v1-baseline/` | Initial API version | Baseline establishment |
| `api-evolution/v2-compatible/` | Compatible changes | Safe evolution patterns |
| `multi-service/user-service/` | User management API | Service design patterns |
| `multi-service/shared-types/` | Common definitions | Shared library patterns |

### 🚀 Advanced Examples
| Example | Description | Key Features |
|---------|-------------|--------------|
| `api-evolution/v3-breaking/` | Breaking changes | Migration strategies |
| `oras-registry/private-deps/` | Private registries | Enterprise patterns |
| `advanced-features/custom-plugins/` | Custom validation | Plugin development |
| `ci-cd-patterns/github-actions/` | CI integration | Automated workflows |

## 🧪 Testing & Validation

All examples include comprehensive testing to ensure they work correctly:

### Build Validation
```bash
# Test all examples build successfully
./test/run_buf_integration_tests.py

# Test specific category
./test/run_buf_integration_tests.py --category=quickstart
./test/run_buf_integration_tests.py --category=api-evolution
./test/run_buf_integration_tests.py --category=multi-service
```

### Performance Testing
```bash
# Run performance benchmarks
./test/run_performance_tests.py

# Test ORAS registry performance
./test/run_oras_performance_tests.py
```

### Integration Testing
```bash
# End-to-end integration tests
./test/run_integration_tests.py

# Registry connectivity tests
./test/run_registry_tests.py
```

## 🎯 Real-World Scenarios

These examples are based on realistic scenarios you'll encounter in production:

### 📱 E-Commerce Platform
- **User Service**: Authentication, profiles, preferences
- **Order Service**: Shopping cart, order management, fulfillment
- **Payment Service**: Payment processing, billing, subscriptions
- **Shared Types**: Common domain objects and error types

### 🔄 API Evolution Journey
- **v1 Baseline**: Initial API design with basic functionality
- **v2 Compatible**: Adding new features while maintaining compatibility
- **v3 Breaking**: Major refactoring with proper migration strategy

### 🏢 Enterprise Integration
- **Private Registries**: Internal API libraries and shared schemas
- **Team Workflows**: Multi-team development and collaboration
- **Security Patterns**: API security, authentication, authorization
- **Compliance**: Regulatory requirements and audit trails

## 🔧 Configuration Examples

### Lint Configuration Patterns
```yaml
# Basic linting
lint:
  use:
    - DEFAULT
    - COMMENTS
    - FIELD_NAMES_LOWER_SNAKE_CASE

# Strict linting for production APIs
lint:
  use:
    - DEFAULT
    - COMMENTS
    - FIELD_NAMES_LOWER_SNAKE_CASE
    - SERVICE_NAMES_PASCAL_CASE
    - ENUM_NAMES_UPPER_SNAKE_CASE
  except:
    - PACKAGE_VERSION_SUFFIX
  enum_zero_value_suffix: _UNSPECIFIED
  service_suffix: Service
```

### Breaking Change Configuration
```yaml
# Wire compatibility (recommended for APIs)
breaking:
  use:
    - WIRE_COMPATIBLE
    - WIRE_JSON_COMPATIBLE
  except:
    - FIELD_SAME_DEFAULT

# Source compatibility (for internal libraries)
breaking:
  use:
    - SOURCE_COMPATIBLE
  ignore:
    - internal/**/*.proto
```

### Multi-Module Workspace
```yaml
# buf.work.yaml
version: v1
directories:
  - user-service
  - order-service
  - payment-service
  - shared-types
```

## 🚀 Getting Started

1. **Choose your starting point** based on your experience level
2. **Follow the examples** in the recommended learning path
3. **Adapt patterns** to your specific use case
4. **Contribute improvements** back to the community

## 📚 Additional Resources

- **[Buf Rules Documentation](../../docs/buf-rules.md)** - Complete rule reference
- **[ORAS Registry Guide](../../docs/oras-client.md)** - Registry setup and usage
- **[Performance Guide](../../docs/performance.md)** - Optimization strategies
- **[Troubleshooting Guide](../../docs/troubleshooting.md)** - Common issues and solutions

## 🤝 Contributing

Found an issue or have an improvement? 

1. **Report bugs** in the project issue tracker
2. **Suggest enhancements** via feature requests
3. **Contribute examples** following the established patterns
4. **Improve documentation** to help other users

---

**These examples demonstrate the power and flexibility of buf integration with buck2-protobuf. Start with the quickstart examples and progress through the learning path to master modern protobuf development! 🚀**
