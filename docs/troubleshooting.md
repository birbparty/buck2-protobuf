# Troubleshooting Guide

Common issues and solutions for the Buck2 protobuf integration.

## Table of Contents

- [Build Errors](#build-errors)
- [Tool Issues](#tool-issues)
- [Language-Specific Issues](#language-specific-issues)
- [Performance Issues](#performance-issues)
- [Advanced Debugging](#advanced-debugging)

---

## Build Errors

### "protoc not found" Error

**Symptom:**
```
Error: protoc not found in PATH
Build failed: Unable to execute protoc
```

**Causes & Solutions:**

1. **Buck2 configuration missing protobuf cell:**
   ```ini
   # Add to .buckconfig
   [cells]
   protobuf = third-party/buck2-protobuf
   ```

2. **Tool download failed:**
   ```bash
   # Manual tool verification
   buck2 run @protobuf//tools:validate_tools
   
   # Force tool re-download
   buck2 clean
   buck2 build @protobuf//tools:download_protoc
   ```

3. **Platform detection issue:**
   ```bash
   # Check platform detection
   buck2 cquery @protobuf//platforms:default --output-attributes
   
   # Override platform if needed
   buck2 build --target-platforms=@protobuf//platforms:linux_x86_64 //your:target
   ```

---

### "proto file not found" Error

**Symptom:**
```
Error: user.proto: File not found.
Error: Import "common/base.proto" was not found or had errors.
```

**Causes & Solutions:**

1. **Missing proto_library dependency:**
   ```python
   # ❌ Wrong - missing dependency
   proto_library(
       name = "user_proto",
       srcs = ["user.proto"],  # imports common/base.proto
   )
   
   # ✅ Correct - include dependency
   proto_library(
       name = "user_proto",
       srcs = ["user.proto"],
       deps = ["//common:base_proto"],  # Add missing dependency
   )
   ```

2. **Incorrect import path:**
   ```protobuf
   // ❌ Wrong - absolute path
   import "src/common/base.proto";
   
   // ✅ Correct - relative to proto_path
   import "common/base.proto";
   ```

3. **Missing visibility:**
   ```python
   # ❌ Wrong - dependency not visible
   proto_library(
       name = "base_proto",
       srcs = ["base.proto"],
       visibility = ["//visibility:private"],  # Too restrictive
   )
   
   # ✅ Correct - make dependency visible
   proto_library(
       name = "base_proto", 
       srcs = ["base.proto"],
       visibility = ["PUBLIC"],  # Or specific targets
   )
   ```

---

### "duplicate symbol" or "redefinition" Errors

**Symptom:**
```
Error: "User" is already defined in file "user.proto".
Error: Package "user.v1" is already defined.
```

**Causes & Solutions:**

1. **Duplicate proto files in different targets:**
   ```python
   # ❌ Wrong - same proto in multiple targets
   proto_library(name = "lib1", srcs = ["user.proto"])
   proto_library(name = "lib2", srcs = ["user.proto"])  # Duplicate!
   
   # ✅ Correct - single proto_library, multiple language targets
   proto_library(name = "user_proto", srcs = ["user.proto"])
   go_proto_library(name = "user_go", proto = ":user_proto")
   python_proto_library(name = "user_py", proto = ":user_proto")
   ```

2. **Conflicting package names:**
   ```protobuf
   // ❌ Wrong - different files with same package
   // File: user.proto
   package user.v1;
   
   // File: account.proto  
   package user.v1;  // Conflict!
   
   // ✅ Correct - unique packages
   // File: user.proto
   package user.v1;
   
   // File: account.proto
   package account.v1;
   ```

---

## Tool Issues

### Tool Download Failures

**Symptom:**
```
Error downloading protoc: HTTP 404
Checksum mismatch for downloaded tool
```

**Solutions:**

1. **Check internet connectivity:**
   ```bash
   # Test direct download
   curl -L https://github.com/protocolbuffers/protobuf/releases/latest
   ```

2. **Verify tool configuration:**
   ```bash
   # Check tool versions
   cat tools/platforms/common.bzl | grep -A 5 "PROTOC_VERSION"
   
   # Manually validate checksums
   buck2 run @protobuf//tools:validate_tools
   ```

3. **Use corporate proxy/mirror:**
   ```ini
   # Add to .buckconfig
   [build]
   tool_cache_dir = /path/to/corporate/cache
   
   [download]
   proxy = http://proxy.company.com:8080
   ```

---

### Plugin Execution Failures

**Symptom:**
```
protoc-gen-go: plugin failed with status 1
protoc-gen-grpc-python: command not found
```

**Solutions:**

1. **Plugin not installed:**
   ```bash
   # For Go plugins
   go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
   go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
   
   # For Python plugins  
   pip install grpcio-tools
   ```

2. **Plugin not in PATH:**
   ```python
   # Use explicit plugin paths
   go_proto_library(
       name = "user_go",
       proto = ":user_proto",
       options = {
           "go_protoc_gen_go_path": "/usr/local/bin/protoc-gen-go",
           "go_protoc_gen_grpc_path": "/usr/local/bin/protoc-gen-go-grpc",
       },
   )
   ```

---

## Language-Specific Issues

### Go Issues

**Import path resolution problems:**

```
Error: cannot find package "github.com/org/proto/v1"
```

**Solutions:**

1. **Explicit go_package option:**
   ```python
   proto_library(
       name = "user_proto",
       srcs = ["user.proto"],
       options = {
           "go_package": "github.com/your-org/protos/user/v1",
       },
   )
   ```

2. **go.mod generation:**
   ```python
   go_proto_library(
       name = "user_go",
       proto = ":user_proto", 
       go_module = "github.com/your-org/protos",
       go_package = "github.com/your-org/protos/user/v1",
   )
   ```

### Python Issues

**Module import errors:**

```
ModuleNotFoundError: No module named 'user_pb2'
ImportError: cannot import name 'UserServiceStub' from 'user_pb2_grpc'
```

**Solutions:**

1. **Check Python package structure:**
   ```python
   python_proto_library(
       name = "user_py",
       proto = ":user_proto",
       python_package = "myapp.protos.user.v1",
       generate_stubs = True,
   )
   ```

2. **Verify __init__.py generation:**
   ```bash
   # Check generated package structure
   ls -la buck-out/gen/user_py/python/
   # Should include __init__.py, py.typed
   ```

### TypeScript Issues

**Type definition problems:**

```
TS2307: Cannot find module '@org/user-protos'
TS2345: Argument of type 'string' is not assignable to parameter of type 'UserRequest'
```

**Solutions:**

1. **Generate declaration files:**
   ```python
   typescript_proto_library(
       name = "user_ts",
       proto = ":user_proto",
       generate_dts = True,
       npm_package = "@org/user-protos",
   )
   ```

2. **Configure TypeScript paths:**
   ```json
   // tsconfig.json
   {
     "compilerOptions": {
       "paths": {
         "@org/user-protos": ["./buck-out/gen/user_ts/typescript"]
       }
     }
   }
   ```

---

## Performance Issues

### Slow Build Times

**Symptom:**
Build takes > 30 seconds for small proto changes.

**Diagnosis:**
```bash
# Profile build performance
buck2 build //your:target --show-slower-than=1s -v 2

# Check cache hit rate
buck2 status --show-cache-stats
```

**Solutions:**

1. **Optimize proto structure:**
   ```python
   # ❌ Wrong - monolithic proto
   proto_library(
       name = "all_protos",
       srcs = glob(["**/*.proto"]),  # Too broad
   )
   
   # ✅ Correct - granular protos
   proto_library(name = "user_proto", srcs = ["user.proto"])
   proto_library(name = "order_proto", srcs = ["order.proto"])
   ```

2. **Use proto_bundle for multi-language:**
   ```python
   # ❌ Wrong - separate language targets
   go_proto_library(name = "user_go", proto = ":user_proto")
   python_proto_library(name = "user_py", proto = ":user_proto")
   
   # ✅ Correct - parallel generation
   proto_bundle(
       name = "user_bundle",
       proto = ":user_proto",
       languages = {"go": {}, "python": {}},
       parallel_generation = True,
   )
   ```

### Memory Issues

**Symptom:**
```
Out of memory during protoc execution
Buck2 process killed by OOM killer
```

**Solutions:**

1. **Reduce descriptor set size:**
   ```python
   proto_library(
       name = "large_proto",
       srcs = ["large.proto"],
       well_known_types = False,  # Reduce memory usage
   )
   ```

2. **Increase heap size:**
   ```bash
   # Increase Buck2 memory
   export BUCK2_JAVA_ARGS="-Xmx8g"
   buck2 build //your:target
   ```

---

## Advanced Debugging

### Enable Verbose Logging

```bash
# Maximum verbosity
buck2 build //your:target -v 5

# Category-specific logging
buck2 build //your:target --console-type=json | jq '.category'

# Rule execution details
buck2 build //your:target --show-full-command-line
```

### Inspect Generated Files

```bash
# List all generated files
buck2 build //your:target --show-full-output

# Examine specific generated file
buck2 cat-outputs //your:target | grep ".pb.go"

# Compare generated files across changes
buck2 build //your:target
cp -r buck-out/gen/your/target /tmp/before
# Make changes
buck2 build //your:target  
diff -r /tmp/before buck-out/gen/your/target
```

### Debug Tool Execution

```bash
# Run protoc manually with same arguments
buck2 build //your:target --show-full-command-line 2>&1 | \
  grep protoc | head -1 | bash -x

# Check tool versions
buck2 run @protobuf//tools:validate_tools -- --verbose

# Test specific plugin
echo 'syntax = "proto3"; message Test { string field = 1; }' | \
  protoc --proto_path=. --go_out=. --plugin=protoc-gen-go=$(which protoc-gen-go) -
```

### Buck2 Cache Debugging

```bash
# Clear specific target cache
buck2 clean //your:target

# Disable caching for debugging
buck2 build //your:target --no-cache

# Check cache key generation
buck2 cquery //your:target --output-attributes | jq '.cache_key'
```

### Get Help

If you're still having issues:

1. **Check Examples:** Review working examples in `examples/` directory
2. **Search Issues:** Look for similar problems in project issues
3. **Enable Debug Mode:** Use `--verbose` and `--show-full-command-line` flags
4. **Minimal Reproduction:** Create smallest possible failing case
5. **Environment Info:** Include Buck2 version, OS, protoc version

**Useful Debug Commands:**
```bash
# System information
buck2 --version
protoc --version
go version
python --version

# Buck2 configuration
buck2 audit config
buck2 audit cell
cat .buckconfig

# Environment variables
env | grep -E "(BUCK|PROTO|GO|PYTHON)"
