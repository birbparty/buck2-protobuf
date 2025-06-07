# Buck2 Protobuf Rules Reference

Complete API documentation for all protobuf rules in the Buck2 integration.

## Table of Contents

- [Core Rules](#core-rules)
  - [proto_library](#proto_library)
  - [proto_bundle](#proto_bundle)
  - [grpc_service](#grpc_service)
- [Language-Specific Rules](#language-specific-rules)
  - [Go Rules](#go-rules)
  - [Python Rules](#python-rules)
  - [TypeScript Rules](#typescript-rules)
  - [C++ Rules](#cpp-rules)
  - [Rust Rules](#rust-rules)
- [Utility Rules](#utility-rules)
  - [Validation Rules](#validation-rules)
  - [Security Rules](#security-rules)
- [Common Patterns](#common-patterns)
- [Performance Considerations](#performance-considerations)

---

## Core Rules

### proto_library

Defines a protobuf library from `.proto` source files. This is the foundation rule that all language-specific generation rules depend on.

**Load Statement:**
```python
load("@protobuf//rules:proto.bzl", "proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this protobuf library target |
| `srcs` | `list[string]` | ✅ | List of `.proto` files to include in this library |
| `deps` | `list[string]` | ❌ | List of `proto_library` targets that this library depends on |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification (default: `["//visibility:private"]`) |
| `import_prefix` | `string` | ❌ | Prefix to add to all import paths for this library |
| `strip_import_prefix` | `string` | ❌ | Prefix to strip from import paths when resolving |
| `options` | `dict[string, string]` | ❌ | Protobuf options to apply (language-specific packages, etc.) |
| `validation` | `dict[string, string]` | ❌ | Validation configuration options |
| `well_known_types` | `bool` | ❌ | Whether to include Google's well-known types (default: `True`) |
| `protoc_version` | `string` | ❌ | Specific protoc version to use (defaults to global config) |

**Example:**
```python
proto_library(
    name = "user_proto",
    srcs = ["user.proto", "user_types.proto"],
    deps = ["//common:base_proto"],
    options = {
        "go_package": "github.com/org/user/v1",
        "java_package": "com.org.user.v1",
        "python_package": "org.user.v1",
    },
    validation = {
        "enforce_package_naming": "true",
        "allow_deprecated_fields": "false",
    },
    visibility = ["PUBLIC"],
)
```

**Generated Files:**
- Descriptor set (`.descriptorset`) for downstream code generation
- Validation reports (if validation enabled)

---

### proto_bundle

Generates code for multiple languages from a single `proto_library` with consistent configuration and cross-language validation.

**Load Statement:**
```python
load("@protobuf//rules:proto.bzl", "proto_bundle")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Base name for the bundle (individual targets will be suffixed) |
| `proto` | `string` | ✅ | `proto_library` target to generate code from |
| `languages` | `dict[string, dict[string, string]]` | ✅ | Dictionary mapping language names to their configurations |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification applied to all targets |
| `consistency_checks` | `bool` | ❌ | Whether to perform cross-language consistency validation (default: `True`) |
| `parallel_generation` | `bool` | ❌ | Whether to generate language targets in parallel (default: `True`) |

**Generated Targets:**
- `{name}_go` (if "go" language specified)
- `{name}_python` (if "python" language specified)
- `{name}_typescript` (if "typescript" language specified)
- `{name}_cpp` (if "cpp" language specified)
- `{name}_rust` (if "rust" language specified)

**Example:**
```python
proto_bundle(
    name = "user_bundle",
    proto = ":user_proto",
    languages = {
        "go": {
            "go_package": "github.com/org/user/v1",
            "go_module": "github.com/org/user",
        },
        "python": {
            "python_package": "org.user.v1",
            "generate_stubs": "true",
        },
        "typescript": {
            "npm_package": "@org/user-v1",
            "output_format": "es2020",
        },
    },
    consistency_checks = True,
    visibility = ["PUBLIC"],
)
```

---

### grpc_service

Generates gRPC service code with advanced features for specified languages. Supports plugins like gRPC-Gateway, OpenAPI documentation, validation, and mock generation.

**Load Statement:**
```python
load("@protobuf//rules:proto.bzl", "grpc_service")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Target name for the service bundle |
| `proto` | `string` | ✅ | `proto_library` target containing service definitions |
| `languages` | `list[string]` | ✅ | List of languages to generate code for |
| `plugins` | `dict[string, dict[string, string]]` | ❌ | Plugin configurations for advanced features |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `service_config` | `dict[string, string]` | ❌ | Service-specific configuration options |

**Supported Plugins:**

| Plugin | Languages | Description |
|--------|-----------|-------------|
| `grpc-gateway` | Go | HTTP/JSON to gRPC proxy generation |
| `openapi` | All | OpenAPI/Swagger documentation |
| `validate` | Go, Python | Request/response validation |
| `mock` | All | Mock implementations for testing |
| `grpc-web` | TypeScript | Browser gRPC clients |

**Example:**
```python
grpc_service(
    name = "user_service",
    proto = ":user_service_proto",
    languages = ["go", "python", "typescript"],
    plugins = {
        "grpc-gateway": {
            "enabled": "true",
            "openapi_output": "true",
        },
        "validate": {
            "emit_imported_vars": "true",
            "lang": "go",
        },
        "mock": {
            "package": "usermocks",
            "source": "interface",
        },
    },
    visibility = ["PUBLIC"],
)
```

---

## Language-Specific Rules

### Go Rules

#### go_proto_library

Generates Go code from a `proto_library` target with full gRPC support.

**Load Statement:**
```python
load("@protobuf//rules:go.bzl", "go_proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this Go protobuf library target |
| `proto` | `string` | ✅ | `proto_library` target to generate Go code from |
| `go_package` | `string` | ❌ | Go package path override (e.g., "github.com/org/pkg/v1") |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `plugins` | `list[string]` | ❌ | List of protoc plugins to use (default: `["go", "go-grpc"]`) |
| `options` | `dict[string, string]` | ❌ | Additional protoc options for Go generation |
| `go_module` | `string` | ❌ | Go module name for generated `go.mod` file |
| `embed` | `list[string]` | ❌ | Additional files to include in the Go package |

**Example:**
```python
go_proto_library(
    name = "user_go_proto",
    proto = ":user_proto",
    go_package = "github.com/org/user/v1",
    go_module = "github.com/org/user",
    plugins = ["go", "go-grpc"],
    options = {
        "go_paths": "source_relative",
        "go_grpc_require_unimplemented_servers": "false",
    },
    visibility = ["PUBLIC"],
)
```

**Generated Files:**
- `*.pb.go` - Basic protobuf message code (protoc-gen-go)
- `*_grpc.pb.go` - gRPC service stubs (protoc-gen-go-grpc)
- `go.mod` - Go module definition (if `go_module` specified)

#### go_proto_messages

Convenience wrapper that generates only Go protobuf message code (no gRPC services).

**Example:**
```python
go_proto_messages(
    name = "user_messages_go",
    proto = ":user_proto",
    go_package = "github.com/org/user/v1/messages",
    visibility = ["PUBLIC"],
)
```

#### go_grpc_library

Convenience wrapper that ensures both protobuf messages and gRPC service stubs are generated.

**Example:**
```python
go_grpc_library(
    name = "user_service_go",
    proto = ":user_service_proto",
    go_package = "github.com/org/user/service/v1",
    visibility = ["PUBLIC"],
)
```

---

### Python Rules

#### python_proto_library

Generates Python code from a `proto_library` target with comprehensive mypy type checking support.

**Load Statement:**
```python
load("@protobuf//rules:python.bzl", "python_proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this Python protobuf library target |
| `proto` | `string` | ✅ | `proto_library` target to generate Python code from |
| `python_package` | `string` | ❌ | Python package path override (e.g., "myapp.protos.v1") |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `plugins` | `list[string]` | ❌ | List of protoc plugins to use (default: `["python", "grpc-python"]`) |
| `generate_stubs` | `bool` | ❌ | Whether to generate `.pyi` type stub files (default: `True`) |
| `mypy_support` | `bool` | ❌ | Whether to enable mypy compatibility features (default: `True`) |
| `options` | `dict[string, string]` | ❌ | Additional protoc options for Python generation |

**Example:**
```python
python_proto_library(
    name = "user_py_proto",
    proto = ":user_proto",
    python_package = "myapp.protos.user.v1",
    plugins = ["python", "grpc-python"],
    generate_stubs = True,
    mypy_support = True,
    visibility = ["PUBLIC"],
)
```

**Generated Files:**
- `*_pb2.py` - Basic protobuf message code
- `*_pb2_grpc.py` - gRPC service stubs
- `*_pb2.pyi` - Type stubs for basic protobuf code
- `*_pb2_grpc.pyi` - Type stubs for gRPC service code
- `__init__.py` - Python package initialization
- `py.typed` - PEP 561 typed package marker

#### python_proto_messages

Generates only Python protobuf message code (no gRPC services).

#### python_grpc_library

Generates Python gRPC service stubs with both messages and service definitions.

#### python_proto_mypy

Generates Python protobuf code with enhanced mypy support using protoc-gen-mypy.

---

### TypeScript Rules

#### typescript_proto_library

Generates TypeScript code from a `proto_library` target with gRPC-Web compatibility.

**Load Statement:**
```python
load("@protobuf//rules:typescript.bzl", "typescript_proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this TypeScript protobuf library target |
| `proto` | `string` | ✅ | `proto_library` target to generate TypeScript code from |
| `npm_package` | `string` | ❌ | NPM package name override |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `plugins` | `list[string]` | ❌ | List of protoc plugins to use |
| `output_format` | `string` | ❌ | TypeScript output format (`"es2015"`, `"es2020"`, `"commonjs"`) |
| `generate_dts` | `bool` | ❌ | Whether to generate `.d.ts` declaration files |
| `options` | `dict[string, string]` | ❌ | Additional protoc options |

**Example:**
```python
typescript_proto_library(
    name = "user_ts_proto",
    proto = ":user_proto",
    npm_package = "@org/user-protos",
    output_format = "es2020",
    generate_dts = True,
    visibility = ["PUBLIC"],
)
```

---

### C++ Rules

#### cpp_proto_library

Generates high-performance native C++ code from a `proto_library` target.

**Load Statement:**
```python
load("@protobuf//rules:cpp.bzl", "cpp_proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this C++ protobuf library target |
| `proto` | `string` | ✅ | `proto_library` target to generate C++ code from |
| `namespace` | `string` | ❌ | C++ namespace override |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `plugins` | `list[string]` | ❌ | List of protoc plugins to use |
| `optimization` | `string` | ❌ | Optimization level (`"speed"`, `"code_size"`, `"lite_runtime"`) |
| `options` | `dict[string, string]` | ❌ | Additional protoc options |

**Example:**
```python
cpp_proto_library(
    name = "user_cpp_proto",
    proto = ":user_proto",
    namespace = "org::user::v1",
    optimization = "speed",
    visibility = ["PUBLIC"],
)
```

---

### Rust Rules

#### rust_proto_library

Generates Rust code from a `proto_library` target with Prost and Tonic integration.

**Load Statement:**
```python
load("@protobuf//rules:rust.bzl", "rust_proto_library")
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | `string` | ✅ | Unique name for this Rust protobuf library target |
| `proto` | `string` | ✅ | `proto_library` target to generate Rust code from |
| `rust_package` | `string` | ❌ | Rust package name override |
| `visibility` | `list[string]` | ❌ | Buck2 visibility specification |
| `plugins` | `list[string]` | ❌ | List of protoc plugins to use |
| `prost_config` | `dict[string, string]` | ❌ | Prost-specific configuration |
| `tonic_config` | `dict[string, string]` | ❌ | Tonic gRPC configuration |

**Example:**
```python
rust_proto_library(
    name = "user_rust_proto",
    proto = ":user_proto",
    rust_package = "user_proto",
    plugins = ["prost", "tonic"],
    visibility = ["PUBLIC"],
)
```

---

## Common Patterns

### Single Proto File
```python
# Define the proto library
proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

# Generate for specific language
go_proto_library(
    name = "user_go",
    proto = ":user_proto",
    go_package = "github.com/org/user/v1",
)
```

### Multi-Language Bundle
```python
# Generate for multiple languages at once
proto_bundle(
    name = "user_bundle",
    proto = ":user_proto",
    languages = {
        "go": {"go_package": "github.com/org/user/v1"},
        "python": {"python_package": "org.user.v1"},
        "typescript": {"npm_package": "@org/user-v1"},
    },
    visibility = ["PUBLIC"],
)
```

### gRPC Service with Gateway
```python
# Full-featured gRPC service
grpc_service(
    name = "user_service",
    proto = ":user_service_proto",
    languages = ["go", "python"],
    plugins = {
        "grpc-gateway": {"enabled": "true"},
        "openapi": {"output_format": "json"},
    },
    visibility = ["PUBLIC"],
)
```

### Proto Dependencies
```python
# Base proto library
proto_library(
    name = "base_proto",
    srcs = ["base.proto"],
    visibility = ["PUBLIC"],
)

# Derived proto library
proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    deps = [":base_proto"],
    visibility = ["PUBLIC"],
)
```

---

## Performance Considerations

### Build Performance

- **Use proto_bundle** for multi-language generation to enable parallel compilation
- **Minimize dependencies** between proto libraries to reduce incremental build scope
- **Enable caching** through Buck2's built-in caching system

### Runtime Performance

- **C++ optimization**: Use `optimization = "speed"` for performance-critical paths
- **Lite runtime**: Use `optimization = "lite_runtime"` for mobile/embedded use cases
- **Go optimization**: Use `plugins = ["go"]` only if gRPC is not needed

### Memory Usage

- **Lazy loading**: Enable lazy field loading for large messages
- **Arena allocation**: Use arena allocation for C++ when handling many messages
- **Streaming**: Prefer streaming APIs for large data transfers

---

## Validation and Security

All rules support built-in validation and security features:

- **Proto linting** with buf integration
- **Security scanning** of generated code
- **Sandboxed execution** of all tools
- **Dependency validation** for supply chain security

For detailed configuration, see the [Validation Guide](validation.md) and [Security Guide](security.md).
