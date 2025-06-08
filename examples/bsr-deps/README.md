# BSR Dependencies Examples

This directory demonstrates how to use BSR (Buf Schema Registry) dependencies with buck2-protobuf, showcasing integration with popular public BSR modules and ORAS caching optimization.

## Overview

The BSR dependency resolution system allows you to consume protobuf dependencies directly from the Buf Schema Registry, with automatic ORAS caching for performance optimization. This connects buck2-protobuf to the modern protobuf ecosystem.

## Supported Dependencies

Currently supported popular BSR dependencies:

- **buf.build/googleapis/googleapis** - Google APIs
- **buf.build/grpc-ecosystem/grpc-gateway** - gRPC-Gateway HTTP/JSON proxy
- **buf.build/envoyproxy/protoc-gen-validate** - Protocol Buffer validation
- **buf.build/connectrpc/connect** - Connect protocol support

## Basic Usage

### Simple API with googleapis

```python
proto_library(
    name = "api_proto",
    srcs = ["api_service.proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",
    ],
    options = {
        "go_package": "github.com/example/api/v1",
    },
    visibility = ["PUBLIC"],
)
```

### gRPC Service with Gateway Support

```python
proto_library(
    name = "gateway_service_proto",
    srcs = ["gateway_service.proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",
        "buf.build/grpc-ecosystem/grpc-gateway",
    ],
    options = {
        "go_package": "github.com/example/gateway/v1",
    },
    visibility = ["PUBLIC"],
)
```

### Service with Validation

```python
proto_library(
    name = "validated_service_proto", 
    srcs = ["validated_service.proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",
        "buf.build/envoyproxy/protoc-gen-validate",
    ],
    options = {
        "go_package": "github.com/example/validated/v1",
    },
    visibility = ["PUBLIC"],
)
```

## Version Specification

You can specify versions for BSR dependencies:

```python
proto_library(
    name = "versioned_proto",
    srcs = ["service.proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis:main",           # Latest
        "buf.build/grpc-ecosystem/grpc-gateway:v2.0.0",  # Specific version
    ],
    visibility = ["PUBLIC"],
)
```

## Multi-Service Architecture

The examples demonstrate how to share BSR dependencies across multiple services:

```python
# Common types used by multiple services
proto_library(
    name = "common_types_proto",
    srcs = ["common_types.proto"],
    bsr_deps = ["buf.build/googleapis/googleapis"],
    visibility = ["PUBLIC"],
)

# User service with validation
proto_library(
    name = "user_service_proto",
    srcs = ["user_service.proto"],
    deps = [":common_types_proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",
        "buf.build/envoyproxy/protoc-gen-validate",
    ],
    visibility = ["PUBLIC"],
)

# Order service with gateway support
proto_library(
    name = "order_service_proto",
    srcs = ["order_service.proto"], 
    deps = [":common_types_proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",
        "buf.build/grpc-ecosystem/grpc-gateway",
    ],
    visibility = ["PUBLIC"],
)
```

## Performance Features

### ORAS Caching

BSR dependencies are automatically cached using ORAS (OCI Registry As Storage) for optimal performance:

- **Content-addressable storage**: Dependencies are cached by content hash
- **Team optimization**: Shared cache across team members
- **Bandwidth efficiency**: Content deduplication reduces download times
- **Cache hits < 200ms**: Fast resolution for cached dependencies

### Parallel Resolution

Multiple BSR dependencies are resolved in parallel for optimal build times:

```python
proto_library(
    name = "performance_test_proto",
    srcs = ["performance_test.proto"],
    bsr_deps = [
        "buf.build/googleapis/googleapis",           # Resolved in parallel
        "buf.build/grpc-ecosystem/grpc-gateway",     # Resolved in parallel  
        "buf.build/envoyproxy/protoc-gen-validate",  # Resolved in parallel
        "buf.build/connectrpc/connect",              # Resolved in parallel
    ],
    visibility = ["PUBLIC"],
)
```

## Language Integration

BSR dependencies work seamlessly with language-specific code generation:

```python
# Go integration
go_proto_library(
    name = "gateway_service_go",
    proto = ":gateway_service_proto",
    visibility = ["PUBLIC"],
)

# Python integration  
python_proto_library(
    name = "validated_service_python",
    proto = ":validated_service_proto",
    visibility = ["PUBLIC"],
)
```

## File Structure

```
examples/bsr-deps/
├── BUCK                      # Buck2 build definitions
├── README.md                 # This documentation
├── api_service.proto         # Basic googleapis integration
├── gateway_service.proto     # gRPC-Gateway integration
├── validated_service.proto   # Validation integration
├── complete_service.proto    # All BSR dependencies
├── user_service.proto        # Multi-service example
├── order_service.proto       # Multi-service example
├── common_types.proto        # Shared types
└── performance_test.proto    # Performance testing
```

## Build Commands

```bash
# Build basic API example
buck2 build //examples/bsr-deps:api_with_googleapis

# Build gateway service with Go code generation
buck2 build //examples/bsr-deps:gateway_service_go

# Build validated service with Python code generation
buck2 build //examples/bsr-deps:validated_service_python

# Build complete service with all dependencies
buck2 build //examples/bsr-deps:complete_service_proto

# Performance test with many dependencies
buck2 build //examples/bsr-deps:performance_test_proto
```

## Performance Targets

The BSR dependency resolution system meets these performance targets:

- **BSR dependency resolution**: < 2s for 10 dependencies
- **ORAS cache hit**: < 200ms
- **Content deduplication**: Reduces bandwidth usage
- **Parallel resolution**: Optimized for multiple dependencies

## Troubleshooting

### Cache Issues

Clear BSR cache if you encounter stale dependency issues:

```bash
python3 tools/oras_bsr.py clear-cache --older-than 7
```

### Dependency Information

Get information about supported dependencies:

```bash
# List all supported dependencies
python3 tools/oras_bsr.py list

# Get info about specific dependency
python3 tools/oras_bsr.py info buf.build/googleapis/googleapis
```

### Network Issues

If BSR dependency resolution fails due to network issues, the system will:

1. First try to resolve via buf CLI
2. Fall back to ORAS cache if available
3. Create placeholder proto files for known dependencies
4. Provide clear error messages for debugging

## Contributing

To add support for new BSR dependencies:

1. Add the dependency to `SUPPORTED_DEPENDENCIES` in `tools/oras_bsr.py`
2. Add expected proto files in `rules/private/bsr_impl.bzl`
3. Create placeholder proto content if needed
4. Add test cases in `tools/test_oras_bsr.py`
5. Update documentation

## Next Steps

This BSR dependency resolution implementation provides the foundation for:

- Private BSR repository support (Task #12)
- BSR authentication system (Task #12)
- Advanced BSR features and team workflows
- Community adoption of BSR ecosystem

The system demonstrates buck2-protobuf alignment with modern protobuf practices and provides significant performance benefits through ORAS caching and content deduplication.
