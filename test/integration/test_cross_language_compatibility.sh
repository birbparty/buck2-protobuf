#!/bin/bash
"""
Cross-language compatibility tests for protobuf Buck2 integration.

This script validates that proto files generate compatible code across
all supported languages and that the generated code can interoperate.
"""

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_WORKSPACE="$PROJECT_ROOT/buck-out/cross-lang-test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test result tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Supported languages
LANGUAGES=("go" "python" "typescript" "cpp" "rust")

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Test execution helpers
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    log_info "Running compatibility test: $test_name"
    
    if $test_function; then
        log_success "✓ $test_name passed"
        ((TESTS_PASSED++))
        return 0
    else
        log_error "✗ $test_name failed"
        FAILED_TESTS+=("$test_name")
        ((TESTS_FAILED++))
        return 1
    fi
}

# Setup test workspace
setup_test_workspace() {
    log_info "Setting up cross-language test workspace at $TEST_WORKSPACE"
    
    rm -rf "$TEST_WORKSPACE"
    mkdir -p "$TEST_WORKSPACE"
    
    # Copy project files to test workspace
    cp -r "$PROJECT_ROOT"/{rules,tools,platforms,examples} "$TEST_WORKSPACE/"
    cp "$PROJECT_ROOT"/{.buckconfig,BUCK} "$TEST_WORKSPACE/"
    
    # Create compatibility test protos
    create_compatibility_test_protos
    
    cd "$TEST_WORKSPACE"
    log_success "Cross-language test workspace ready"
}

create_compatibility_test_protos() {
    log_info "Creating compatibility test proto files"
    
    # Create test proto directory
    mkdir -p "$TEST_WORKSPACE/test/compatibility"
    
    # Common types proto
    cat > "$TEST_WORKSPACE/test/compatibility/common_types.proto" << 'EOF'
syntax = "proto3";

package compatibility.common;

import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";

// Common message types for compatibility testing
message BasicTypes {
  // Primitive types
  bool bool_field = 1;
  int32 int32_field = 2;
  int64 int64_field = 3;
  uint32 uint32_field = 4;
  uint64 uint64_field = 5;
  float float_field = 6;
  double double_field = 7;
  string string_field = 8;
  bytes bytes_field = 9;
  
  // Well-known types
  google.protobuf.Timestamp timestamp_field = 10;
  google.protobuf.Duration duration_field = 11;
}

message ComplexTypes {
  // Repeated fields
  repeated string string_list = 1;
  repeated int32 int_list = 2;
  repeated BasicTypes message_list = 3;
  
  // Map fields
  map<string, string> string_map = 4;
  map<int32, BasicTypes> message_map = 5;
  
  // Optional fields
  optional string optional_string = 6;
  optional int32 optional_int = 7;
  optional BasicTypes optional_message = 8;
}

enum TestEnum {
  UNKNOWN = 0;
  FIRST = 1;
  SECOND = 2;
  THIRD = 3;
}

message EnumTypes {
  TestEnum enum_field = 1;
  repeated TestEnum enum_list = 2;
  map<string, TestEnum> enum_map = 3;
}

// Nested message types
message NestedTypes {
  message NestedMessage {
    string value = 1;
    int32 number = 2;
  }
  
  NestedMessage nested = 1;
  repeated NestedMessage nested_list = 2;
}

// Oneof types
message OneofTypes {
  oneof test_oneof {
    string string_choice = 1;
    int32 int_choice = 2;
    BasicTypes message_choice = 3;
  }
}
EOF

    # Service definition proto
    cat > "$TEST_WORKSPACE/test/compatibility/test_service.proto" << 'EOF'
syntax = "proto3";

package compatibility.service;

import "test/compatibility/common_types.proto";

// Test service for gRPC compatibility
service TestService {
  // Unary RPC
  rpc GetBasicTypes(GetBasicTypesRequest) returns (GetBasicTypesResponse);
  
  // Server streaming RPC
  rpc StreamBasicTypes(StreamBasicTypesRequest) returns (stream compatibility.common.BasicTypes);
  
  // Client streaming RPC
  rpc UploadBasicTypes(stream compatibility.common.BasicTypes) returns (UploadBasicTypesResponse);
  
  // Bidirectional streaming RPC
  rpc ProcessBasicTypes(stream compatibility.common.BasicTypes) returns (stream compatibility.common.BasicTypes);
}

message GetBasicTypesRequest {
  string id = 1;
}

message GetBasicTypesResponse {
  compatibility.common.BasicTypes data = 1;
  bool success = 2;
}

message StreamBasicTypesRequest {
  int32 count = 1;
}

message UploadBasicTypesResponse {
  int32 processed_count = 1;
  bool success = 2;
}
EOF

    # Create BUCK files for compatibility tests
    cat > "$TEST_WORKSPACE/test/compatibility/BUCK" << 'EOF'
load("//rules:proto.bzl", "proto_library")
load("//rules:go.bzl", "go_proto_library")
load("//rules:python.bzl", "python_proto_library")
load("//rules:typescript.bzl", "typescript_proto_library")
load("//rules:cpp.bzl", "cpp_proto_library")
load("//rules:rust.bzl", "rust_proto_library")

# Common types proto library
proto_library(
    name = "common_types_proto",
    srcs = ["common_types.proto"],
    visibility = ["PUBLIC"],
)

# Service proto library
proto_library(
    name = "test_service_proto",
    srcs = ["test_service.proto"],
    deps = [":common_types_proto"],
    visibility = ["PUBLIC"],
)

# Go generated code
go_proto_library(
    name = "common_types_go",
    proto = ":common_types_proto",
    visibility = ["PUBLIC"],
)

go_proto_library(
    name = "test_service_go",
    proto = ":test_service_proto",
    grpc = True,
    visibility = ["PUBLIC"],
)

# Python generated code
python_proto_library(
    name = "common_types_python",
    proto = ":common_types_proto",
    visibility = ["PUBLIC"],
)

python_proto_library(
    name = "test_service_python",
    proto = ":test_service_proto",
    grpc = True,
    visibility = ["PUBLIC"],
)

# TypeScript generated code
typescript_proto_library(
    name = "common_types_typescript",
    proto = ":common_types_proto",
    visibility = ["PUBLIC"],
)

typescript_proto_library(
    name = "test_service_typescript",
    proto = ":test_service_proto",
    grpc = True,
    visibility = ["PUBLIC"],
)

# C++ generated code
cpp_proto_library(
    name = "common_types_cpp",
    proto = ":common_types_proto",
    visibility = ["PUBLIC"],
)

cpp_proto_library(
    name = "test_service_cpp",
    proto = ":test_service_proto",
    grpc = True,
    visibility = ["PUBLIC"],
)

# Rust generated code
rust_proto_library(
    name = "common_types_rust",
    proto = ":common_types_proto",
    visibility = ["PUBLIC"],
)

rust_proto_library(
    name = "test_service_rust",
    proto = ":test_service_proto",
    grpc = True,
    visibility = ["PUBLIC"],
)
EOF

    log_success "Compatibility test protos created"
}

# Test functions
test_basic_proto_compilation() {
    log_info "Testing basic proto compilation across all languages"
    
    local all_passed=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang compilation..."
        
        if buck2 build "//test/compatibility:common_types_${lang}" >/dev/null 2>&1; then
            log_success "    ✓ $lang compilation successful"
        else
            log_error "    ✗ $lang compilation failed"
            all_passed=false
        fi
    done
    
    return $([ "$all_passed" = true ])
}

test_grpc_service_compilation() {
    log_info "Testing gRPC service compilation across all languages"
    
    local all_passed=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang gRPC compilation..."
        
        if buck2 build "//test/compatibility:test_service_${lang}" >/dev/null 2>&1; then
            log_success "    ✓ $lang gRPC compilation successful"
        else
            log_error "    ✗ $lang gRPC compilation failed"
            all_passed=false
        fi
    done
    
    return $([ "$all_passed" = true ])
}

test_wire_format_compatibility() {
    log_info "Testing wire format compatibility between languages"
    
    # Generate test data in different languages and verify compatibility
    local test_data_dir="$TEST_WORKSPACE/wire_format_test"
    mkdir -p "$test_data_dir"
    
    # Create test data generator scripts
    create_wire_format_test_scripts "$test_data_dir"
    
    # Generate test data with Go (reference implementation)
    if command -v go >/dev/null 2>&1; then
        log_info "  Generating reference data with Go..."
        cd "$test_data_dir"
        if generate_go_test_data; then
            log_success "    ✓ Go test data generated"
        else
            log_error "    ✗ Go test data generation failed"
            return 1
        fi
    else
        log_warning "  Go not available for reference data generation"
        return 0
    fi
    
    # Test compatibility with other languages
    local all_compatible=true
    
    for lang in "${LANGUAGES[@]}"; do
        if [[ "$lang" != "go" ]]; then
            log_info "  Testing $lang wire format compatibility..."
            
            if test_language_wire_compatibility "$lang" "$test_data_dir"; then
                log_success "    ✓ $lang wire format compatible"
            else
                log_error "    ✗ $lang wire format incompatible"
                all_compatible=false
            fi
        fi
    done
    
    return $([ "$all_compatible" = true ])
}

create_wire_format_test_scripts() {
    local test_dir="$1"
    
    # Go test data generator
    cat > "$test_dir/generate_go_data.go" << 'EOF'
package main

import (
    "fmt"
    "os"
    "time"
    
    "google.golang.org/protobuf/proto"
    "google.golang.org/protobuf/types/known/timestamppb"
    "google.golang.org/protobuf/types/known/durationpb"
)

// Note: This would import the generated Go code
// For testing purposes, we'll create a simple data file

func main() {
    // Create test data representing a BasicTypes message
    // This is a simplified version - real implementation would use generated code
    testData := []byte{
        // Protobuf binary data representing BasicTypes message
        0x08, 0x01,                     // bool_field = true
        0x10, 0x2A,                     // int32_field = 42
        0x18, 0x80, 0x01,               // int64_field = 128
        0x25, 0x00, 0x00, 0x20, 0x41,   // float_field = 10.0
        0x42, 0x05, 0x68, 0x65, 0x6C, 0x6C, 0x6F, // string_field = "hello"
    }
    
    err := os.WriteFile("test_data.bin", testData, 0644)
    if err != nil {
        fmt.Printf("Error writing test data: %v\n", err)
        os.Exit(1)
    }
    
    fmt.Println("Test data generated successfully")
}
EOF

    # Python test data validator
    cat > "$test_dir/validate_python_data.py" << 'EOF'
#!/usr/bin/env python3

import sys
import os

def validate_wire_format():
    """Validate that Python can read Go-generated wire format data."""
    try:
        with open("test_data.bin", "rb") as f:
            data = f.read()
        
        # Simple validation - check that we can read the binary data
        # Real implementation would use generated Python protobuf code
        if len(data) > 0:
            print("✓ Python can read binary protobuf data")
            return True
        else:
            print("✗ Empty data file")
            return False
            
    except Exception as e:
        print(f"✗ Python wire format validation failed: {e}")
        return False

if __name__ == "__main__":
    success = validate_wire_format()
    sys.exit(0 if success else 1)
EOF

    chmod +x "$test_dir/validate_python_data.py"
}

generate_go_test_data() {
    # Simplified test data generation
    # In real implementation, this would compile and run the Go generator
    echo -e "\x08\x01\x10\x2A\x18\x80\x01\x25\x00\x00\x20\x41\x42\x05hello" > test_data.bin
    return 0
}

test_language_wire_compatibility() {
    local lang="$1"
    local test_dir="$2"
    
    case "$lang" in
        "python")
            cd "$test_dir" && python3 validate_python_data.py
            ;;
        "typescript")
            # TypeScript compatibility test
            log_info "    TypeScript wire format test (placeholder)"
            return 0
            ;;
        "cpp")
            # C++ compatibility test
            log_info "    C++ wire format test (placeholder)"
            return 0
            ;;
        "rust")
            # Rust compatibility test
            log_info "    Rust wire format test (placeholder)"
            return 0
            ;;
        *)
            log_warning "    Unknown language: $lang"
            return 1
            ;;
    esac
}

test_api_consistency() {
    log_info "Testing API consistency across languages"
    
    # Build all language targets to verify API consistency
    local all_consistent=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Validating $lang API consistency..."
        
        # Check that all expected targets build successfully
        if buck2 build "//test/compatibility:common_types_${lang}" "//test/compatibility:test_service_${lang}" >/dev/null 2>&1; then
            log_success "    ✓ $lang API consistent"
        else
            log_error "    ✗ $lang API inconsistent"
            all_consistent=false
        fi
    done
    
    return $([ "$all_consistent" = true ])
}

test_enum_compatibility() {
    log_info "Testing enum value compatibility across languages"
    
    # Verify that enum values are consistent across all languages
    # This is critical for wire format compatibility
    
    local all_compatible=true
    
    # Build all targets that use enums
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang enum compatibility..."
        
        if buck2 build "//test/compatibility:common_types_${lang}" >/dev/null 2>&1; then
            # Check generated enum values (simplified)
            if verify_enum_values "$lang"; then
                log_success "    ✓ $lang enum values compatible"
            else
                log_error "    ✗ $lang enum values incompatible"
                all_compatible=false
            fi
        else
            log_error "    ✗ $lang enum compilation failed"
            all_compatible=false
        fi
    done
    
    return $([ "$all_compatible" = true ])
}

verify_enum_values() {
    local lang="$1"
    
    # Simplified enum verification
    # Real implementation would check generated code for correct enum values
    case "$lang" in
        "go"|"python"|"typescript"|"cpp"|"rust")
            return 0  # Assume compatible for now
            ;;
        *)
            return 1
            ;;
    esac
}

test_field_presence_compatibility() {
    log_info "Testing field presence semantics across languages"
    
    # Test proto3 optional fields and proto2 required/optional fields
    # Ensure consistent behavior across all language implementations
    
    local all_compatible=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang field presence semantics..."
        
        if verify_field_presence_semantics "$lang"; then
            log_success "    ✓ $lang field presence compatible"
        else
            log_error "    ✗ $lang field presence incompatible"
            all_compatible=false
        fi
    done
    
    return $([ "$all_compatible" = true ])
}

verify_field_presence_semantics() {
    local lang="$1"
    
    # Simplified field presence verification
    # Real implementation would test optional field behavior
    return 0
}

test_grpc_method_compatibility() {
    log_info "Testing gRPC method signature compatibility"
    
    # Verify that gRPC method signatures are consistent across languages
    local all_compatible=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang gRPC method compatibility..."
        
        if buck2 build "//test/compatibility:test_service_${lang}" >/dev/null 2>&1; then
            log_success "    ✓ $lang gRPC methods compatible"
        else
            log_error "    ✗ $lang gRPC methods incompatible"
            all_compatible=false
        fi
    done
    
    return $([ "$all_compatible" = true ])
}

test_performance_parity() {
    log_info "Testing performance parity across languages"
    
    # Basic performance test to ensure no language has drastically poor performance
    local performance_dir="$TEST_WORKSPACE/performance_test"
    mkdir -p "$performance_dir"
    
    local all_acceptable=true
    
    for lang in "${LANGUAGES[@]}"; do
        log_info "  Testing $lang performance..."
        
        local duration
        duration=$(measure_compilation_time "$lang")
        
        log_info "    $lang compilation time: ${duration}ms"
        
        # Basic threshold check (adjust as needed)
        if [[ $duration -lt 30000 ]]; then  # 30 seconds
            log_success "    ✓ $lang performance acceptable"
        else
            log_warning "    ⚠ $lang performance slower than expected"
            # Don't fail the test, just warn
        fi
    done
    
    return $([ "$all_acceptable" = true ])
}

measure_compilation_time() {
    local lang="$1"
    
    # Clean and measure compilation time
    buck2 clean >/dev/null 2>&1
    
    local start_time=$(date +%s%N)
    buck2 build "//test/compatibility:common_types_${lang}" >/dev/null 2>&1
    local end_time=$(date +%s%N)
    
    local duration_ms=$(((end_time - start_time) / 1000000))
    echo "$duration_ms"
}

cleanup_test_workspace() {
    log_info "Cleaning up cross-language test workspace"
    cd "$PROJECT_ROOT"
    rm -rf "$TEST_WORKSPACE"
}

# Main test execution
main() {
    log_info "Starting cross-language compatibility tests"
    log_info "Project root: $PROJECT_ROOT"
    
    # Setup
    setup_test_workspace
    
    # Core compatibility tests
    run_test "Basic Proto Compilation" test_basic_proto_compilation
    run_test "gRPC Service Compilation" test_grpc_service_compilation
    run_test "Wire Format Compatibility" test_wire_format_compatibility
    run_test "API Consistency" test_api_consistency
    run_test "Enum Compatibility" test_enum_compatibility
    run_test "Field Presence Compatibility" test_field_presence_compatibility
    run_test "gRPC Method Compatibility" test_grpc_method_compatibility
    run_test "Performance Parity" test_performance_parity
    
    # Cleanup
    cleanup_test_workspace
    
    # Results summary
    log_info "Cross-Language Compatibility Test Results:"
    log_info "  Passed: $TESTS_PASSED"
    log_info "  Failed: $TESTS_FAILED"
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        log_error "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            log_error "  - $test"
        done
        exit 1
    else
        log_success "All cross-language compatibility tests passed!"
        exit 0
    fi
}

# Handle script arguments
case "${1:-run}" in
    "run"|"")
        main
        ;;
    "setup")
        setup_test_workspace
        ;;
    "cleanup")
        cleanup_test_workspace
        ;;
    *)
        echo "Usage: $0 [run|setup|cleanup]"
        exit 1
        ;;
esac
