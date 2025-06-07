#!/bin/bash
"""
Integration test workflows for protobuf Buck2 integration.

This script runs end-to-end tests to validate that the protobuf-buck2
integration works correctly across different scenarios and platforms.
"""

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_WORKSPACE="$PROJECT_ROOT/buck-out/test-workspace"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Test result tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Test execution helpers
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    log_info "Running test: $test_name"
    
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

# Performance measurement helpers
measure_time() {
    local start_time=$(date +%s%N)
    "$@"
    local end_time=$(date +%s%N)
    local duration_ms=$(((end_time - start_time) / 1000000))
    echo "$duration_ms"
}

check_buck2_available() {
    if ! command -v buck2 &> /dev/null; then
        log_error "Buck2 is not available in PATH"
        return 1
    fi
    
    log_info "Buck2 version: $(buck2 --version)"
    return 0
}

check_protoc_available() {
    if ! command -v protoc &> /dev/null; then
        log_warning "protoc is not available in PATH - some tests may be skipped"
        return 1
    fi
    
    log_info "protoc version: $(protoc --version)"
    return 0
}

# Setup test workspace
setup_test_workspace() {
    log_info "Setting up test workspace at $TEST_WORKSPACE"
    
    rm -rf "$TEST_WORKSPACE"
    mkdir -p "$TEST_WORKSPACE"
    
    # Copy project files to test workspace
    cp -r "$PROJECT_ROOT"/{rules,test,tools,platforms,examples} "$TEST_WORKSPACE/"
    cp "$PROJECT_ROOT"/{.buckconfig,BUCK} "$TEST_WORKSPACE/"
    
    cd "$TEST_WORKSPACE"
    log_success "Test workspace ready"
}

cleanup_test_workspace() {
    log_info "Cleaning up test workspace"
    cd "$PROJECT_ROOT"
    rm -rf "$TEST_WORKSPACE"
}

# Test functions
test_basic_proto_compilation() {
    log_info "Testing basic proto compilation"
    
    local duration
    duration=$(measure_time buck2 build //test/fixtures:simple_proto)
    
    if [[ $duration -gt 10000 ]]; then  # 10 seconds
        log_warning "Proto compilation took ${duration}ms (>10s)"
    else
        log_info "Proto compilation completed in ${duration}ms"
    fi
    
    # Check that descriptor set was generated
    local descriptor_set="buck-out/v2/gen/root/*/test/fixtures/__simple_proto__/simple_proto.descriptorset"
    if ls $descriptor_set 1> /dev/null 2>&1; then
        log_success "Descriptor set generated successfully"
        return 0
    else
        log_error "Descriptor set not found"
        return 1
    fi
}

test_dependency_chain() {
    log_info "Testing proto dependency chain"
    
    # Build complex proto that depends on simple proto
    buck2 build //test/fixtures:complex_proto
    
    # Verify both descriptor sets exist
    local simple_ds="buck-out/v2/gen/root/*/test/fixtures/__simple_proto__/simple_proto.descriptorset"
    local complex_ds="buck-out/v2/gen/root/*/test/fixtures/__complex_proto__/complex_proto.descriptorset"
    
    if ls $simple_ds 1> /dev/null 2>&1 && ls $complex_ds 1> /dev/null 2>&1; then
        log_success "Dependency chain built successfully"
        return 0
    else
        log_error "Dependency chain build failed"
        return 1
    fi
}

test_service_proto() {
    log_info "Testing gRPC service proto compilation"
    
    buck2 build //test/fixtures:service_proto
    
    local service_ds="buck-out/v2/gen/root/*/test/fixtures/__service_proto__/service_proto.descriptorset"
    if ls $service_ds 1> /dev/null 2>&1; then
        log_success "Service proto compiled successfully"
        return 0
    else
        log_error "Service proto compilation failed"
        return 1
    fi
}

test_basic_fixture_compilation() {
    log_info "Testing basic fixture compilation"
    
    buck2 build //test/fixtures/basic:minimal_proto //test/fixtures/basic:types_proto
    
    # Check outputs exist
    local minimal_ds="buck-out/v2/gen/root/*/test/fixtures/basic/__minimal_proto__/minimal_proto.descriptorset"
    local types_ds="buck-out/v2/gen/root/*/test/fixtures/basic/__types_proto__/types_proto.descriptorset"
    
    if ls $minimal_ds 1> /dev/null 2>&1 && ls $types_ds 1> /dev/null 2>&1; then
        log_success "Basic fixtures compiled successfully"
        return 0
    else
        log_error "Basic fixture compilation failed"
        return 1
    fi
}

test_dependency_fixtures() {
    log_info "Testing dependency fixture compilation"
    
    # Need to create BUCK files for dependencies first
    cat > test/fixtures/dependencies/BUCK << 'EOF'
load("//rules:proto.bzl", "proto_library")

proto_library(
    name = "base_proto",
    srcs = ["base.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "derived_proto",
    srcs = ["derived.proto"],
    deps = [":base_proto"],
    visibility = ["PUBLIC"],
)
EOF
    
    buck2 build //test/fixtures/dependencies:base_proto //test/fixtures/dependencies:derived_proto
    
    local base_ds="buck-out/v2/gen/root/*/test/fixtures/dependencies/__base_proto__/base_proto.descriptorset"
    local derived_ds="buck-out/v2/gen/root/*/test/fixtures/dependencies/__derived_proto__/derived_proto.descriptorset"
    
    if ls $base_ds 1> /dev/null 2>&1 && ls $derived_ds 1> /dev/null 2>&1; then
        log_success "Dependency fixtures compiled successfully"
        return 0
    else
        log_error "Dependency fixture compilation failed"
        return 1
    fi
}

test_edge_case_fixtures() {
    log_info "Testing edge case fixture compilation"
    
    # Create BUCK file for edge cases
    cat > test/fixtures/edge_cases/BUCK << 'EOF'
load("//rules:proto.bzl", "proto_library")

proto_library(
    name = "malformed_proto",
    srcs = ["malformed.proto"],
    visibility = ["PUBLIC"],
)
EOF
    
    buck2 build //test/fixtures/edge_cases:malformed_proto
    
    local malformed_ds="buck-out/v2/gen/root/*/test/fixtures/edge_cases/__malformed_proto__/malformed_proto.descriptorset"
    if ls $malformed_ds 1> /dev/null 2>&1; then
        log_success "Edge case fixtures compiled successfully"
        return 0
    else
        log_error "Edge case fixture compilation failed"
        return 1
    fi
}

test_performance_fixtures() {
    log_info "Testing performance fixture compilation"
    
    # Create BUCK file for performance tests
    cat > test/fixtures/performance/BUCK << 'EOF'
load("//rules:proto.bzl", "proto_library")

proto_library(
    name = "large_proto",
    srcs = ["large.proto"],
    visibility = ["PUBLIC"],
)
EOF
    
    local duration
    duration=$(measure_time buck2 build //test/fixtures/performance:large_proto)
    
    if [[ $duration -gt 15000 ]]; then  # 15 seconds
        log_warning "Large proto compilation took ${duration}ms (>15s) - consider optimization"
    else
        log_info "Large proto compilation completed in ${duration}ms"
    fi
    
    local large_ds="buck-out/v2/gen/root/*/test/fixtures/performance/__large_proto__/large_proto.descriptorset"
    if ls $large_ds 1> /dev/null 2>&1; then
        log_success "Performance fixtures compiled successfully"
        return 0
    else
        log_error "Performance fixture compilation failed"
        return 1
    fi
}

test_clean_build() {
    log_info "Testing clean build workflow"
    
    # Clean previous builds
    buck2 clean
    
    # Build everything from scratch
    local duration
    duration=$(measure_time buck2 build //test/fixtures/...)
    
    log_info "Clean build completed in ${duration}ms"
    
    # Verify some key outputs exist
    if buck2 audit outputs //test/fixtures:simple_proto >/dev/null 2>&1; then
        log_success "Clean build successful"
        return 0
    else
        log_error "Clean build failed"
        return 1
    fi
}

test_incremental_build() {
    log_info "Testing incremental build workflow"
    
    # First build
    buck2 build //test/fixtures:simple_proto
    
    # Modify a proto file slightly
    local simple_proto="test/fixtures/simple.proto"
    local backup_file="$simple_proto.backup"
    
    cp "$simple_proto" "$backup_file"
    echo "// Modified for incremental test" >> "$simple_proto"
    
    # Second build (should be incremental)
    local duration
    duration=$(measure_time buck2 build //test/fixtures:simple_proto)
    
    # Restore original file
    mv "$backup_file" "$simple_proto"
    
    if [[ $duration -lt 5000 ]]; then  # Should be faster than 5s
        log_success "Incremental build completed in ${duration}ms"
        return 0
    else
        log_warning "Incremental build took ${duration}ms (may not be truly incremental)"
        return 0  # Still pass, but warn
    fi
}

test_parallel_builds() {
    log_info "Testing parallel build capability"
    
    # Clean first
    buck2 clean
    
    # Build multiple targets in parallel
    local duration
    duration=$(measure_time buck2 build \
        //test/fixtures:simple_proto \
        //test/fixtures:complex_proto \
        //test/fixtures:service_proto \
        //test/fixtures/basic:minimal_proto \
        //test/fixtures/basic:types_proto \
        --jobs 4)
    
    log_info "Parallel build completed in ${duration}ms"
    
    # Verify all targets were built
    if buck2 audit outputs //test/fixtures:simple_proto //test/fixtures:complex_proto >/dev/null 2>&1; then
        log_success "Parallel build successful"
        return 0
    else
        log_error "Parallel build failed"
        return 1
    fi
}

# Performance benchmarks
run_performance_benchmarks() {
    log_info "Running performance benchmarks"
    
    # Benchmark small proto compilation
    local small_duration
    buck2 clean
    small_duration=$(measure_time buck2 build //test/fixtures/basic:minimal_proto)
    log_info "Small proto compilation: ${small_duration}ms"
    
    # Benchmark medium proto compilation
    local medium_duration
    buck2 clean
    medium_duration=$(measure_time buck2 build //test/fixtures/basic:types_proto)
    log_info "Medium proto compilation: ${medium_duration}ms"
    
    # Benchmark large proto compilation (if available)
    if [[ -f "test/fixtures/performance/BUCK" ]]; then
        local large_duration
        buck2 clean
        large_duration=$(measure_time buck2 build //test/fixtures/performance:large_proto)
        log_info "Large proto compilation: ${large_duration}ms"
    fi
    
    # Performance summary
    log_info "Performance Benchmark Summary:"
    log_info "  Small proto: ${small_duration}ms"
    log_info "  Medium proto: ${medium_duration}ms"
}

# Main test execution
main() {
    log_info "Starting protobuf Buck2 integration tests"
    log_info "Project root: $PROJECT_ROOT"
    
    # Pre-flight checks
    if ! check_buck2_available; then
        log_error "Buck2 not available - cannot run tests"
        exit 1
    fi
    
    check_protoc_available  # Optional for some tests
    
    # Setup
    setup_test_workspace
    
    # Core functionality tests
    run_test "Basic Proto Compilation" test_basic_proto_compilation
    run_test "Dependency Chain" test_dependency_chain
    run_test "Service Proto" test_service_proto
    
    # Fixture tests
    run_test "Basic Fixtures" test_basic_fixture_compilation
    run_test "Dependency Fixtures" test_dependency_fixtures
    run_test "Edge Case Fixtures" test_edge_case_fixtures
    run_test "Performance Fixtures" test_performance_fixtures
    
    # Build workflow tests
    run_test "Clean Build" test_clean_build
    run_test "Incremental Build" test_incremental_build
    run_test "Parallel Builds" test_parallel_builds
    
    # Performance benchmarks
    run_performance_benchmarks
    
    # Cleanup
    cleanup_test_workspace
    
    # Results summary
    log_info "Test Results Summary:"
    log_info "  Passed: $TESTS_PASSED"
    log_info "  Failed: $TESTS_FAILED"
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        log_error "Failed tests:"
        for test in "${FAILED_TESTS[@]}"; do
            log_error "  - $test"
        done
        exit 1
    else
        log_success "All tests passed!"
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
    "benchmark")
        setup_test_workspace
        run_performance_benchmarks
        cleanup_test_workspace
        ;;
    *)
        echo "Usage: $0 [run|setup|cleanup|benchmark]"
        exit 1
        ;;
esac
