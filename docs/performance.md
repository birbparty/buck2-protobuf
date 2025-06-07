# Performance Optimization Guide

Comprehensive guide to achieving optimal performance with the Buck2 protobuf integration.

## Table of Contents

- [Performance Targets](#performance-targets)
- [Build Performance](#build-performance)
- [Runtime Performance](#runtime-performance)
- [Memory Optimization](#memory-optimization)
- [Monitoring and Profiling](#monitoring-and-profiling)
- [Platform-Specific Optimizations](#platform-specific-optimizations)

---

## Performance Targets

### Build Time Targets

| Project Size | Cold Build | Incremental Build | Target |
|--------------|------------|-------------------|---------|
| Small (1-10 files) | < 5s | < 500ms | ✅ Achievable |
| Medium (10-100 files) | < 30s | < 2s | ✅ Achievable |
| Large (100-1000 files) | < 2min | < 10s | ✅ Achievable |
| Enterprise (1000+ files) | < 10min | < 30s | 🎯 Target |

### Runtime Performance Targets

| Language | Message Creation | Serialization | Deserialization |
|----------|------------------|---------------|-----------------|
| C++ | < 10ns | < 100ns/KB | < 150ns/KB |
| Go | < 50ns | < 200ns/KB | < 300ns/KB |
| Rust | < 20ns | < 120ns/KB | < 180ns/KB |
| Python | < 500ns | < 1µs/KB | < 1.5µs/KB |
| TypeScript | < 100ns | < 400ns/KB | < 600ns/KB |

---

## Build Performance

### 1. Optimize Proto Structure

**Use Granular Proto Libraries**

```python
# ❌ Poor: Monolithic proto library
proto_library(
    name = "all_protos",
    srcs = glob(["**/*.proto"]),  # Rebuilds everything on any change
    visibility = ["PUBLIC"],
)

# ✅ Good: Granular proto libraries
proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "order_proto", 
    srcs = ["order.proto"],
    deps = [":user_proto"],  # Only depend on what's needed
    visibility = ["PUBLIC"],
)

proto_library(
    name = "payment_proto",
    srcs = ["payment.proto"],
    deps = [":user_proto"],
    visibility = ["PUBLIC"],
)
```

**Minimize Cross-Dependencies**

```python
# ❌ Poor: Circular or unnecessary dependencies
proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    deps = [":order_proto"],  # Creates circular dependency
)

proto_library(
    name = "order_proto",
    srcs = ["order.proto"], 
    deps = [":user_proto", ":payment_proto", ":notification_proto"],  # Too many deps
)

# ✅ Good: Layered architecture
proto_library(
    name = "common_proto",
    srcs = ["common.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "user_proto",
    srcs = ["user.proto"],
    deps = [":common_proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "order_proto",
    srcs = ["order.proto"],
    deps = [":user_proto"],  # Only what's needed
    visibility = ["PUBLIC"],
)
```

### 2. Leverage Parallel Generation

**Use proto_bundle for Multi-Language**

```python
# ❌ Poor: Sequential language generation
go_proto_library(
    name = "user_go",
    proto = ":user_proto",
)

python_proto_library(
    name = "user_py", 
    proto = ":user_proto",
)

typescript_proto_library(
    name = "user_ts",
    proto = ":user_proto",
)

# ✅ Good: Parallel language generation
proto_bundle(
    name = "user_bundle",
    proto = ":user_proto",
    languages = {
        "go": {"go_package": "github.com/org/user/v1"},
        "python": {"python_package": "org.user.v1"},
        "typescript": {"npm_package": "@org/user-v1"},
    },
    parallel_generation = True,  # Enable parallel compilation
    visibility = ["PUBLIC"],
)
```

### 3. Optimize Caching

**Configure Buck2 Cache Settings**

```ini
# .buckconfig
[cache]
# Enable remote caching for team builds
mode = dir
dir = /shared/buck2-cache

# Local cache optimization
local_cache_size_limit = 10GB
artifact_cache_size_limit = 50GB

# Enable incremental builds
incremental = true

[build]
# Parallel execution
threads = 8

# Memory allocation
heap_size = 8GB
```

**Use Cache-Friendly Patterns**

```python
# ✅ Good: Stable dependencies reduce cache misses
proto_library(
    name = "stable_api_proto",
    srcs = ["stable_api.proto"],
    # No frequently changing dependencies
    visibility = ["PUBLIC"],
)

proto_library(
    name = "experimental_proto",
    srcs = ["experimental.proto"],
    deps = [":stable_api_proto"],  # Depend on stable APIs
    visibility = ["PUBLIC"],
)
```

### 4. Tool Optimization

**Configure Tool Performance**

```python
# Optimize protoc execution
go_proto_library(
    name = "user_go",
    proto = ":user_proto",
    options = {
        # Reduce protoc overhead
        "go_opt": "paths=source_relative",
        # Disable unnecessary features for performance
        "go_grpc_opt": "require_unimplemented_servers=false",
    },
)
```

---

## Runtime Performance

### 1. Language-Specific Optimizations

#### C++ Performance

```python
cpp_proto_library(
    name = "high_perf_cpp",
    proto = ":user_proto",
    optimization = "speed",  # Optimize for speed over size
    options = {
        # Enable arena allocation for better memory performance
        "cpp_enable_arenas": "true",
        # Use lite runtime for mobile/embedded
        "cpp_lite": "false",  # Full runtime for features
        # Optimize string handling
        "cpp_string_type": "string",
    },
)
```

**C++ Usage Patterns:**

```cpp
// Use arena allocation for message-heavy code
google::protobuf::Arena arena;
User* user = google::protobuf::Arena::CreateMessage<User>(&arena);
user->set_name("John Doe");
// Arena automatically cleans up all messages

// Reuse message objects
User user;
for (const auto& data : batch_data) {
    user.Clear();  // Faster than creating new instances
    user.ParseFromString(data);
    ProcessUser(user);
}
```

#### Go Performance

```python
go_proto_library(
    name = "optimized_go",
    proto = ":user_proto",
    options = {
        # Use optimized paths
        "go_opt": "paths=source_relative",
        # Reduce reflection overhead
        "go_opt": "Muser.proto=./user",
    },
)
```

**Go Usage Patterns:**

```go
// Use sync.Pool for frequent allocations
var userPool = sync.Pool{
    New: func() interface{} {
        return &User{}
    },
}

func ProcessUsers(data [][]byte) {
    for _, d := range data {
        user := userPool.Get().(*User)
        if err := proto.Unmarshal(d, user); err != nil {
            userPool.Put(user)
            continue
        }
        
        // Process user...
        
        user.Reset()  // Clear for reuse
        userPool.Put(user)
    }
}

// Use specific field access for performance
func GetUserName(user *User) string {
    if user != nil && user.Name != nil {
        return *user.Name  // Direct field access
    }
    return ""
}
```

#### Python Performance

```python
python_proto_library(
    name = "optimized_py",
    proto = ":user_proto",
    options = {
        # Use C++ implementation for performance
        "python_implementation": "cpp",
        # Optimize for speed
        "python_optimize_for": "SPEED",
    },
)
```

**Python Usage Patterns:**

```python
# Use message factories for better performance
from google.protobuf.message_factory import MessageFactory
from google.protobuf.descriptor_pool import DescriptorPool

pool = DescriptorPool()
factory = MessageFactory(pool)

# Batch operations
users = []
for i in range(1000):
    user = User()  # Reuse message type
    user.id = str(i)
    user.name = f"User {i}"
    users.append(user.SerializeToString())

# Use BytesIO for streaming
import io
buffer = io.BytesIO()
for user_data in users:
    buffer.write(user_data)
```

### 2. Message Design for Performance

**Optimize Field Types**

```protobuf
syntax = "proto3";

message OptimizedUser {
    // ✅ Use fixed-size types for better performance
    fixed64 id = 1;           // Better than int64 for large numbers
    string name = 2;          // Required field, good
    
    // ✅ Use repeated primitive types efficiently
    repeated fixed32 scores = 3;  // Packed by default in proto3
    
    // ✅ Group related fields
    message Address {
        string street = 1;
        string city = 2;
        fixed32 zip_code = 3;
    }
    Address address = 4;
    
    // ❌ Avoid deep nesting for performance
    // message Level1 {
    //     message Level2 {
    //         message Level3 {  // Too deep
    //             string value = 1;
    //         }
    //     }
    // }
}
```

**Use Appropriate Field Numbers**

```protobuf
message PerformantMessage {
    // ✅ Use 1-15 for frequently accessed fields (1 byte encoding)
    string critical_field = 1;
    int32 important_id = 2;
    
    // ✅ Use 16+ for less frequent fields
    string optional_metadata = 16;
    repeated string tags = 17;
    
    // ❌ Don't skip low numbers unnecessarily
    // string rarely_used = 100;  // Wastes efficient encoding
}
```

---

## Memory Optimization

### 1. Message Lifecycle Management

**C++ Memory Management**

```cpp
// Use smart pointers for automatic cleanup
std::unique_ptr<User> CreateUser() {
    return std::make_unique<User>();
}

// Use arena allocation for bulk operations
void ProcessManyUsers(const std::vector<std::string>& data) {
    google::protobuf::Arena arena;
    
    for (const auto& user_data : data) {
        User* user = google::protobuf::Arena::CreateMessage<User>(&arena);
        user->ParseFromString(user_data);
        // Process user...
    }
    // Arena automatically cleans up all users
}
```

**Go Memory Management**

```go
// Reset messages instead of creating new ones
func ProcessUserBatch(data [][]byte) {
    user := &User{}
    
    for _, d := range data {
        user.Reset()  // Clear previous data
        if err := proto.Unmarshal(d, user); err != nil {
            continue
        }
        // Process user...
    }
}

// Use specific types to reduce allocations
type UserProcessor struct {
    user *User
}

func NewUserProcessor() *UserProcessor {
    return &UserProcessor{
        user: &User{},
    }
}

func (p *UserProcessor) Process(data []byte) error {
    p.user.Reset()
    return proto.Unmarshal(data, p.user)
}
```

### 2. Streaming for Large Data

**Use Streaming APIs**

```python
# For large datasets, use streaming
def process_large_user_file(filename):
    with open(filename, 'rb') as f:
        while True:
            # Read size prefix
            size_data = f.read(4)
            if not size_data:
                break
                
            size = struct.unpack('<I', size_data)[0]
            user_data = f.read(size)
            
            user = User()
            user.ParseFromString(user_data)
            
            # Process user immediately, don't accumulate
            process_user(user)
            del user  # Explicit cleanup
```

---

## Monitoring and Profiling

### 1. Build Performance Monitoring

**Buck2 Performance Analysis**

```bash
# Enable detailed timing
buck2 build //your:target --show-slower-than=1s -v 2

# Profile specific rules
buck2 build //your:target --profile=proto_generation

# Cache hit rate analysis
buck2 status --show-cache-stats

# Memory usage monitoring
buck2 build //your:target --heap-profile=/tmp/buck2-heap.prof
```

**Custom Performance Metrics**

```python
# Add performance monitoring to rules
def _performance_aware_proto_library_impl(ctx):
    start_time = time.time()
    
    # ... normal rule implementation ...
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Log slow builds
    if duration > 10.0:  # 10 seconds threshold
        print("WARNING: Slow proto build detected: {}s for {}".format(
            duration, ctx.label
        ))
    
    return providers
```

### 2. Runtime Performance Monitoring

**Go Performance Monitoring**

```go
import (
    "time"
    "log"
    "github.com/prometheus/client_golang/prometheus"
)

var (
    protoSerializeTime = prometheus.NewHistogramVec(
        prometheus.HistogramOpts{
            Name: "proto_serialize_duration_seconds",
            Help: "Time spent serializing protobuf messages",
        },
        []string{"message_type"},
    )
)

func SerializeUser(user *User) ([]byte, error) {
    start := time.Now()
    defer func() {
        protoSerializeTime.WithLabelValues("User").Observe(
            time.Since(start).Seconds(),
        )
    }()
    
    return proto.Marshal(user)
}
```

**Python Performance Monitoring**

```python
import time
import logging
from functools import wraps

def monitor_proto_performance(message_type):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            
            if duration > 0.1:  # Log slow operations
                logging.warning(
                    f"Slow proto operation: {func.__name__} "
                    f"took {duration:.3f}s for {message_type}"
                )
            
            return result
        return wrapper
    return decorator

@monitor_proto_performance("User")
def serialize_user(user):
    return user.SerializeToString()
```

---

## Platform-Specific Optimizations

### 1. Linux Optimizations

```ini
# .buckconfig for Linux
[build]
# Use all available cores
threads = 0  # Auto-detect

# Optimize for Linux filesystem
use_watchman = true

# Enable faster linking
use_limited_hybrid_linking = true

[cache]
# Use faster filesystem for cache
dir = /dev/shm/buck2-cache  # RAM disk for fastest access
```

### 2. macOS Optimizations

```ini
# .buckconfig for macOS
[build]
# Account for macOS thread limitations
threads = 12  # Conservative for macOS

# Use native file watching
use_watchman = true

[apple]
# Optimize for macOS builds
use_swift_dep_scanner = true
```

### 3. Windows Optimizations

```ini
# .buckconfig for Windows
[build]
# Account for Windows overhead
threads = 8

# Use Windows-specific optimizations
use_windows_symlinks = false

[parser]
# Faster parsing on Windows
num_threads = 4
```

### 4. CI/CD Optimizations

**GitHub Actions Configuration**

```yaml
# .github/workflows/build.yml
name: Optimized Proto Build

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Buck2 Cache
      uses: actions/cache@v3
      with:
        path: |
          ~/.cache/buck2
          /tmp/buck2-cache
        key: buck2-${{ runner.os }}-${{ hashFiles('**/*.bzl', '**/*.proto') }}
        restore-keys: |
          buck2-${{ runner.os }}-
    
    - name: Configure Buck2 for CI
      run: |
        echo "[cache]" >> .buckconfig
        echo "mode = dir" >> .buckconfig
        echo "dir = /tmp/buck2-cache" >> .buckconfig
        echo "[build]" >> .buckconfig
        echo "threads = $(nproc)" >> .buckconfig
    
    - name: Build with performance monitoring
      run: |
        buck2 build //... --show-slower-than=5s
```

---

## Performance Checklist

### Build Performance ✅

- [ ] Use granular proto_library targets
- [ ] Minimize cross-dependencies between protos
- [ ] Use proto_bundle for multi-language generation
- [ ] Enable parallel compilation
- [ ] Configure appropriate Buck2 cache settings
- [ ] Monitor build times and cache hit rates

### Runtime Performance ✅

- [ ] Choose appropriate optimization levels for each language
- [ ] Use efficient message design patterns
- [ ] Implement proper memory management
- [ ] Use streaming for large datasets
- [ ] Monitor serialization/deserialization performance
- [ ] Profile application hotpaths

### Memory Optimization ✅

- [ ] Use arena allocation (C++)
- [ ] Implement object pooling (Go)
- [ ] Reset messages instead of creating new ones
- [ ] Use streaming APIs for large data
- [ ] Monitor memory usage patterns
- [ ] Implement explicit cleanup where needed

### Monitoring ✅

- [ ] Set up build performance monitoring
- [ ] Implement runtime performance metrics
- [ ] Configure alerting for performance regressions
- [ ] Regular performance testing in CI/CD
- [ ] Document performance characteristics
- [ ] Train team on performance best practices

---

For specific performance issues, see the [Troubleshooting Guide](troubleshooting.md) or refer to language-specific optimization guides in the [API Reference](rules-reference.md).
