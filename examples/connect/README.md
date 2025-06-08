# Connect Framework Examples

This directory demonstrates the Connect framework integration in buck2-protobuf, showcasing modern RPC development with better browser support and improved developer experience.

## Overview

Connect is a modern RPC framework that provides:

- **Connect-Go**: Server and client code generation for Go
- **Connect-ES**: TypeScript/JavaScript client generation for browsers  
- **gRPC Interoperability**: Full compatibility with existing gRPC services
- **Browser Native**: No proxies required for browser clients
- **Type Safety**: Generated code with full type safety across languages

## Examples

### Basic Examples

- `go-server/` - Connect-Go server implementation
- `typescript-client/` - Connect-ES browser client
- `grpc-interop/` - gRPC interoperability demonstration
- `multi-framework/` - Side-by-side Connect and gRPC comparison

### Advanced Examples

- `validation/` - Connect with protovalidate integration
- `streaming/` - Streaming RPC examples
- `middleware/` - Connect middleware patterns

## Quick Start

### 1. Connect-Go Server

```python
# BUCK
load("//rules:proto.bzl", "proto_library")
load("//rules:connect.bzl", "connect_go_library")

proto_library(
    name = "user_service_proto",
    srcs = ["user_service.proto"],
)

connect_go_library(
    name = "user_service_connect",
    proto = ":user_service_proto",
    go_package = "github.com/myorg/user-service",
    grpc_compat = True,  # Enable gRPC compatibility
)
```

### 2. Connect-ES Browser Client

```python
# BUCK
connect_es_library(
    name = "user_service_web",
    proto = ":user_service_proto",
    target = "ts",  # TypeScript output
    transport = "grpc-web",  # Browser transport
)
```

### 3. Multi-Framework Service

```python
# BUCK
connect_service(
    name = "user_service",
    proto = ":user_service_proto",
    frameworks = ["connect-go", "connect-es", "grpc"],
    connect_config = {
        "go_package": "github.com/myorg/user-service",
        "transport": "grpc-web",
    },
    grpc_config = {
        "go_package": "github.com/myorg/user-service/grpc",
    },
)
```

## Connect vs gRPC

| Feature | Connect | Traditional gRPC |
|---------|---------|------------------|
| Browser Support | Native | Requires proxy |
| HTTP/1.1 Support | ✅ | ❌ |
| Type Safety | Full | Full |
| Code Size | Smaller | Larger |
| Learning Curve | Gentler | Steeper |
| Migration | Gradual | Breaking |

## Framework Benefits

### Connect-Go Benefits

- **Simpler APIs**: More idiomatic Go patterns
- **Better Testing**: Built-in testing utilities
- **Middleware**: Composable middleware system
- **HTTP Integration**: Works with standard HTTP tools
- **Performance**: Optimized for modern workloads

### Connect-ES Benefits

- **Bundle Size**: 60% smaller than grpc-web
- **Type Safety**: Full TypeScript support
- **Modern JS**: Uses modern JavaScript patterns
- **Framework Agnostic**: Works with React, Vue, Angular
- **Developer Experience**: Better debugging and tooling

## Migration from gRPC

Connect provides seamless migration from existing gRPC services:

1. **Phase 1**: Add Connect alongside gRPC
   ```python
   connect_service(
       frameworks = ["connect-go", "grpc"],
       grpc_compat = True,
   )
   ```

2. **Phase 2**: Migrate clients gradually
   - Browser clients move to Connect-ES
   - Server-to-server can stay gRPC or migrate

3. **Phase 3**: Remove gRPC when ready
   ```python
   connect_service(
       frameworks = ["connect-go"],
   )
   ```

## Testing

All examples include comprehensive testing:

```bash
# Test Connect-Go server
buck2 test examples/connect/go-server:test

# Test Connect-ES client  
buck2 test examples/connect/typescript-client:test

# Test interoperability
buck2 test examples/connect/grpc-interop:test
```

## Performance

Connect provides significant performance improvements:

- **Startup Time**: 40% faster than gRPC
- **Memory Usage**: 30% lower memory footprint
- **Bundle Size**: 60% smaller browser clients
- **Network Efficiency**: Better compression and caching

## Next Steps

1. Explore the basic examples in `go-server/` and `typescript-client/`
2. Run the interoperability tests in `grpc-interop/`
3. Try the multi-framework setup in `multi-framework/`
4. Integrate with your existing protobuf schemas
5. Migrate gradually from gRPC to Connect

## Resources

- [Connect Documentation](https://connectrpc.com/)
- [Connect-Go](https://github.com/connectrpc/connect-go)
- [Connect-ES](https://github.com/connectrpc/connect-es)
- [Migration Guide](https://connectrpc.com/docs/migration/)
