# Migration Guide

Complete guide for migrating from other protobuf build systems to Buck2.

## Table of Contents

- [From Bazel rules_proto](#from-bazel-rules_proto)
- [From Bazel rules_go](#from-bazel-rules_go)
- [From Make/CMake](#from-makecmake)
- [From Gradle protobuf-gradle-plugin](#from-gradle-protobuf-gradle-plugin)
- [Migration Tools](#migration-tools)
- [Common Pitfalls](#common-pitfalls)

---

## From Bazel rules_proto

### Basic proto_library Migration

**Before (Bazel):**
```python
load("@rules_proto//proto:defs.bzl", "proto_library")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    deps = ["@com_google_protobuf//:any_proto"],
)
```

**After (Buck2):**
```python
load("@protobuf//rules:proto.bzl", "proto_library")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    # Well-known types included by default
    visibility = ["PUBLIC"],
)
```

### Go Proto Migration

**Before (Bazel go_proto_library):**
```python
load("@io_bazel_rules_go//proto:def.bzl", "go_proto_library")

go_proto_library(
    name = "user_go_proto",
    proto = ":user_proto",
    importpath = "github.com/org/user",
    visibility = ["//visibility:public"],
)
```

**After (Buck2):**
```python
load("@protobuf//rules:go.bzl", "go_proto_library")

go_proto_library(
    name = "user_go_proto",
    proto = ":user_proto",
    go_package = "github.com/org/user",
    visibility = ["PUBLIC"],
)
```

### gRPC Service Migration

**Before (Bazel):**
```python
load("@com_github_grpc_grpc//bazel:cc_grpc_library.bzl", "cc_grpc_library")

cc_grpc_library(
    name = "user_service_cc_grpc",
    srcs = [":user_service_proto"],
    grpc_only = True,
    deps = [":user_service_cc_proto"],
)
```

**After (Buck2):**
```python
load("@protobuf//rules:cpp.bzl", "cpp_proto_library")

cpp_proto_library(
    name = "user_service_cpp",
    proto = ":user_service_proto",
    plugins = ["cpp", "grpc-cpp"],
    visibility = ["PUBLIC"],
)
```

### Multi-Language Migration

**Before (Bazel - separate targets):**
```python
go_proto_library(name = "user_go", proto = ":user_proto", importpath = "github.com/org/user")
py_proto_library(name = "user_py", deps = [":user_proto"])
java_proto_library(name = "user_java", deps = [":user_proto"])
```

**After (Buck2 - unified bundle):**
```python
load("@protobuf//rules:proto.bzl", "proto_bundle")

proto_bundle(
    name = "user_bundle",
    proto = ":user_proto",
    languages = {
        "go": {"go_package": "github.com/org/user"},
        "python": {"python_package": "org.user"},
        "java": {"java_package": "com.org.user"},
    },
    visibility = ["PUBLIC"],
)
```

---

## From Bazel rules_go

### Go Module Migration

**Before (Bazel):**
```python
# WORKSPACE
go_repository(
    name = "com_github_golang_protobuf",
    importpath = "github.com/golang/protobuf",
    tag = "v1.5.2",
)

# BUILD.bazel
load("@io_bazel_rules_go//go:def.bzl", "go_library")
load("@io_bazel_rules_go//proto:def.bzl", "go_proto_library")

go_proto_library(
    name = "user_go_proto",
    proto = ":user_proto",
    importpath = "github.com/org/user/proto",
)

go_library(
    name = "user",
    srcs = ["user.go"],
    embed = [":user_go_proto"],
    importpath = "github.com/org/user",
)
```

**After (Buck2):**
```python
# BUCK
load("@protobuf//rules:go.bzl", "go_proto_library")

go_proto_library(
    name = "user_go_proto",
    proto = ":user_proto",
    go_package = "github.com/org/user/proto",
    go_module = "github.com/org/user",  # Generates go.mod
    visibility = ["PUBLIC"],
)

# Generated go.mod automatically includes correct dependencies
```

### Go gRPC Migration

**Before (Bazel):**
```python
load("@com_github_grpc_grpc//bazel:go_grpc_library.bzl", "go_grpc_library")

go_grpc_library(
    name = "user_service_go_grpc",
    proto = ":user_service_proto",
    deps = [":user_go_proto"],
)
```

**After (Buck2):**
```python
load("@protobuf//rules:go.bzl", "go_grpc_library")

go_grpc_library(
    name = "user_service_go",
    proto = ":user_service_proto",
    go_package = "github.com/org/user/service",
    visibility = ["PUBLIC"],
)
```

---

## From Make/CMake

### Makefile Migration

**Before (Makefile):**
```makefile
PROTO_SRC = proto
PROTO_OUT = generated
PROTOC = protoc

%.pb.go: %.proto
	$(PROTOC) --proto_path=$(PROTO_SRC) --go_out=$(PROTO_OUT) --go-grpc_out=$(PROTO_OUT) $<

all: user.pb.go order.pb.go

user.pb.go: user.proto
order.pb.go: order.proto user.proto

clean:
	rm -rf $(PROTO_OUT)

.PHONY: all clean
```

**After (Buck2):**
```python
# BUCK
load("@protobuf//rules:proto.bzl", "proto_library")
load("@protobuf//rules:go.bzl", "go_proto_library")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "order_proto", 
    srcs = ["order.proto"],
    deps = [":user_proto"],  # Automatic dependency tracking
    visibility = ["PUBLIC"],
)

go_proto_library(
    name = "user_go",
    proto = ":user_proto",
    go_package = "github.com/org/proto/user",
)

go_proto_library(
    name = "order_go",
    proto = ":order_proto", 
    go_package = "github.com/org/proto/order",
)

# Build: buck2 build //:user_go //:order_go
# Clean: buck2 clean
```

### CMake Migration

**Before (CMakeLists.txt):**
```cmake
find_package(Protobuf REQUIRED)
find_package(gRPC REQUIRED)

set(PROTO_FILES
    user.proto
    order.proto
)

protobuf_generate_cpp(PROTO_SRCS PROTO_HDRS ${PROTO_FILES})
grpc_generate_cpp(GRPC_SRCS GRPC_HDRS ${PROTO_FILES})

add_library(proto_lib ${PROTO_SRCS} ${GRPC_SRCS})
target_link_libraries(proto_lib ${Protobuf_LIBRARIES} ${gRPC_LIBRARIES})
```

**After (Buck2):**
```python
# BUCK
load("@protobuf//rules:proto.bzl", "proto_library")
load("@protobuf//rules:cpp.bzl", "cpp_proto_library")

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "order_proto",
    srcs = ["order.proto"],
    deps = [":user_proto"],
    visibility = ["PUBLIC"],
)

cpp_proto_library(
    name = "proto_lib",
    proto = ":order_proto",  # Includes transitive dependencies
    plugins = ["cpp", "grpc-cpp"],
    visibility = ["PUBLIC"],
)

# Automatic dependency management, no manual linking required
```

---

## From Gradle protobuf-gradle-plugin

### Gradle Build Migration

**Before (build.gradle):**
```groovy
plugins {
    id 'com.google.protobuf' version '0.8.18'
    id 'java'
}

protobuf {
    protoc {
        artifact = 'com.google.protobuf:protoc:3.21.12'
    }
    plugins {
        grpc {
            artifact = 'io.grpc:protoc-gen-grpc-java:1.53.0'
        }
    }
    generateProtoTasks {
        all()*.plugins {
            grpc {}
        }
    }
}

sourceSets {
    main {
        proto {
            srcDir 'src/main/proto'
        }
    }
}

dependencies {
    implementation 'com.google.protobuf:protobuf-java:3.21.12'
    implementation 'io.grpc:grpc-stub:1.53.0'
    implementation 'io.grpc:grpc-protobuf:1.53.0'
}
```

**After (Buck2):**
```python
# BUCK
load("@protobuf//rules:proto.bzl", "proto_library")
load("@protobuf//rules:java.bzl", "java_proto_library")

proto_library(
    name = "service_proto",
    srcs = glob(["src/main/proto/**/*.proto"]),
    visibility = ["PUBLIC"],
)

java_proto_library(
    name = "service_java",
    proto = ":service_proto",
    plugins = ["java", "grpc-java"],
    visibility = ["PUBLIC"],
)

# Dependencies automatically managed
# Build: buck2 build //:service_java
```

### Multi-Module Gradle Migration

**Before (Gradle multi-module):**
```groovy
// settings.gradle
include 'proto-common', 'user-service', 'order-service'

// proto-common/build.gradle
plugins { id 'com.google.protobuf' }

// user-service/build.gradle
dependencies {
    implementation project(':proto-common')
}

// order-service/build.gradle  
dependencies {
    implementation project(':proto-common')
    implementation project(':user-service')
}
```

**After (Buck2):**
```python
# proto-common/BUCK
proto_library(
    name = "common_proto",
    srcs = glob(["*.proto"]),
    visibility = ["PUBLIC"],
)

# user-service/BUCK
proto_library(
    name = "user_service_proto",
    srcs = ["user_service.proto"],
    deps = ["//proto-common:common_proto"],
    visibility = ["PUBLIC"],
)

# order-service/BUCK
proto_library(
    name = "order_service_proto", 
    srcs = ["order_service.proto"],
    deps = [
        "//proto-common:common_proto",
        "//user-service:user_service_proto",
    ],
    visibility = ["PUBLIC"],
)
```

---

## Migration Tools

### Automated Migration Script

```python
#!/usr/bin/env python3
"""
Automated migration tool for converting Bazel BUILD files to Buck2 BUCK files.
"""

import re
import os
import sys
from pathlib import Path

def migrate_bazel_to_buck2(build_content):
    """Convert Bazel BUILD file content to Buck2 BUCK file format."""
    
    # Rule load statements
    migrations = {
        # Proto rules
        r'load\("@rules_proto//proto:defs\.bzl", "proto_library"\)': 
            'load("@protobuf//rules:proto.bzl", "proto_library")',
        
        # Go rules  
        r'load\("@io_bazel_rules_go//proto:def\.bzl", "go_proto_library"\)':
            'load("@protobuf//rules:go.bzl", "go_proto_library")',
        
        # Parameter changes
        r'importpath\s*=': 'go_package =',
        r'//visibility:public': '"PUBLIC"',
        r'@com_google_protobuf//:any_proto': '# Well-known types included by default',
    }
    
    result = build_content
    for pattern, replacement in migrations.items():
        result = re.sub(pattern, replacement, result)
    
    return result

def migrate_workspace_to_buckconfig(workspace_content):
    """Convert WORKSPACE file to .buckconfig format."""
    
    buckconfig = """[cells]
protobuf = third-party/buck2-protobuf

[parser]
target_platform_detector_spec = target:protobuf//platforms:default

[build]
execution_platforms = protobuf//platforms:default
"""
    
    return buckconfig

def main():
    if len(sys.argv) != 2:
        print("Usage: migrate.py <project_directory>")
        sys.exit(1)
    
    project_dir = Path(sys.argv[1])
    
    # Migrate BUILD files to BUCK files
    for build_file in project_dir.rglob("BUILD"):
        buck_file = build_file.parent / "BUCK"
        
        with open(build_file) as f:
            content = f.read()
        
        migrated_content = migrate_bazel_to_buck2(content)
        
        with open(buck_file, 'w') as f:
            f.write(migrated_content)
        
        print(f"Migrated {build_file} -> {buck_file}")
    
    # Convert WORKSPACE to .buckconfig
    workspace_file = project_dir / "WORKSPACE"
    if workspace_file.exists():
        buckconfig_file = project_dir / ".buckconfig"
        
        with open(workspace_file) as f:
            workspace_content = f.read()
        
        buckconfig_content = migrate_workspace_to_buckconfig(workspace_content)
        
        with open(buckconfig_file, 'w') as f:
            f.write(buckconfig_content)
        
        print(f"Created .buckconfig from WORKSPACE")

if __name__ == "__main__":
    main()
```

### Manual Migration Checklist

**Pre-Migration:**
- [ ] Audit current proto dependencies and organization
- [ ] Document custom protoc plugins and configurations
- [ ] Identify performance-critical build paths
- [ ] Plan migration strategy (gradual vs. big-bang)

**During Migration:**
- [ ] Set up Buck2 protobuf cell configuration
- [ ] Convert proto_library targets first
- [ ] Migrate language-specific targets
- [ ] Update import paths and package names
- [ ] Test incremental builds and caching
- [ ] Validate generated code compatibility

**Post-Migration:**
- [ ] Update CI/CD pipelines
- [ ] Train team on new Buck2 workflows
- [ ] Monitor build performance improvements
- [ ] Document new development processes
- [ ] Archive old build system files

---

## Common Pitfalls

### 1. Import Path Issues

**Problem:** Generated code has incorrect import paths after migration.

**Solution:**
```python
# Specify explicit package options
proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    options = {
        "go_package": "github.com/org/user/v1",
        "java_package": "com.org.user.v1", 
        "python_package": "org.user.v1",
    },
)
```

### 2. Dependency Resolution

**Problem:** Proto dependencies not resolving correctly.

**Solution:**
```python
# Use explicit dependencies instead of glob patterns
proto_library(
    name = "order_proto",
    srcs = ["order.proto"], 
    deps = [
        "//common:base_proto",    # Explicit path
        "//user:user_proto",      # Not glob or implicit
    ],
)
```

### 3. Well-Known Types

**Problem:** Missing well-known types (google/protobuf/*.proto).

**Solution:**
```python
# Well-known types are included by default in Buck2
proto_library(
    name = "my_proto",
    srcs = ["my.proto"],
    # No need to explicitly depend on well-known types
    well_known_types = True,  # Default value
)
```

### 4. Plugin Configuration

**Problem:** Custom protoc plugins not working.

**Solution:**
```python
# Configure plugins explicitly
go_proto_library(
    name = "user_go",
    proto = ":user_proto",
    plugins = ["go", "go-grpc", "validate"],  # Specify all needed
    options = {
        "go_opt": "paths=source_relative",
        "validate_opt": "lang=go",
    },
)
```

### 5. Build Performance

**Problem:** Slower builds after migration.

**Solution:**
```python
# Use proto_bundle for parallel generation
proto_bundle(
    name = "user_bundle",
    proto = ":user_proto",
    languages = {"go": {}, "python": {}, "java": {}},
    parallel_generation = True,  # Enable parallelism
)

# Configure Buck2 for performance
# .buckconfig
[build]
threads = 8
[cache] 
mode = dir
dir = /tmp/buck2-cache
```

### 6. Visibility Issues

**Problem:** Build failures due to visibility restrictions.

**Solution:**
```python
# Use PUBLIC for widely used protos
proto_library(
    name = "common_proto",
    srcs = ["common.proto"],
    visibility = ["PUBLIC"],  # Not ["//visibility:public"]
)

# Use specific visibility for internal protos
proto_library(
    name = "internal_proto",
    srcs = ["internal.proto"],
    visibility = ["//internal/...", "//test/..."],
)
```

---

## Migration Timeline

### Week 1: Assessment and Planning
- Audit existing protobuf usage
- Identify migration complexity
- Set up Buck2 protobuf integration
- Plan migration order

### Week 2-3: Core Migration
- Migrate proto_library targets
- Convert language-specific targets
- Update build configurations
- Test basic functionality

### Week 4: Integration and Testing
- Update CI/CD pipelines
- Performance testing and optimization
- Team training and documentation
- Rollback procedures

### Week 5: Production Deployment
- Gradual rollout to production
- Monitor build performance
- Address any issues
- Archive old build system

---

For migration support and specific questions, see the [Troubleshooting Guide](troubleshooting.md) or refer to the [API Reference](rules-reference.md) for detailed rule documentation.
