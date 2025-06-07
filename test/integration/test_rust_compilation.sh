#!/bin/bash

# Integration test for Rust protobuf compilation
# Tests end-to-end compilation of generated Rust code using cargo

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_OUTPUT_DIR="$PROJECT_ROOT/buck-out/test/rust"

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

# Test tracking
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Test result tracking
test_pass() {
    local test_name="$1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log_success "✅ $test_name"
}

test_fail() {
    local test_name="$1"
    local error_msg="$2"
    TESTS_FAILED=$((TESTS_FAILED + 1))
    FAILED_TESTS+=("$test_name: $error_msg")
    log_error "❌ $test_name: $error_msg"
}

# Setup function
setup_test_environment() {
    log_info "Setting up Rust test environment..."
    
    # Check if Rust is installed
    if ! command -v rustc &> /dev/null; then
        log_error "rustc is not installed. Please install Rust toolchain."
        exit 1
    fi
    
    if ! command -v cargo &> /dev/null; then
        log_error "cargo is not installed. Please install Rust toolchain."
        exit 1
    fi
    
    # Check Rust version
    local rust_version=$(rustc --version)
    log_info "Using Rust: $rust_version"
    
    # Create test output directory
    mkdir -p "$TEST_OUTPUT_DIR"
    
    log_success "Test environment setup complete"
}

# Test: Basic Rust message compilation
test_basic_rust_messages() {
    local test_name="Basic Rust Messages"
    log_info "Running test: $test_name"
    
    # Build the Rust proto library
    cd "$PROJECT_ROOT"
    if buck2 build //examples/rust:user_rust_messages &> "$TEST_OUTPUT_DIR/build_messages.log"; then
        local output_dir="$PROJECT_ROOT/buck-out/gen/examples/rust/user_rust_messages/rust"
        
        if [[ -d "$output_dir" ]]; then
            # Check if Cargo.toml exists and is valid
            if [[ -f "$output_dir/Cargo.toml" ]]; then
                cd "$output_dir"
                
                # Try to build with cargo
                if cargo check &> "$TEST_OUTPUT_DIR/cargo_check_messages.log"; then
                    # Check if generated code compiles
                    if cargo build &> "$TEST_OUTPUT_DIR/cargo_build_messages.log"; then
                        test_pass "$test_name"
                        return 0
                    else
                        test_fail "$test_name" "Cargo build failed"
                        cat "$TEST_OUTPUT_DIR/cargo_build_messages.log" | tail -20
                    fi
                else
                    test_fail "$test_name" "Cargo check failed"
                    cat "$TEST_OUTPUT_DIR/cargo_check_messages.log" | tail -20
                fi
            else
                test_fail "$test_name" "Cargo.toml not found"
            fi
        else
            test_fail "$test_name" "Output directory not found: $output_dir"
        fi
    else
        test_fail "$test_name" "Buck2 build failed"
        cat "$TEST_OUTPUT_DIR/build_messages.log" | tail -20
    fi
    
    return 1
}

# Test: Rust gRPC service compilation
test_rust_grpc_services() {
    local test_name="Rust gRPC Services"
    log_info "Running test: $test_name"
    
    # Build the Rust gRPC library
    cd "$PROJECT_ROOT"
    if buck2 build //examples/rust:user_service_rust_grpc &> "$TEST_OUTPUT_DIR/build_grpc.log"; then
        local output_dir="$PROJECT_ROOT/buck-out/gen/examples/rust/user_service_rust_grpc/rust"
        
        if [[ -d "$output_dir" ]]; then
            cd "$output_dir"
            
            # Check if tonic dependencies are present
            if grep -q "tonic" Cargo.toml && grep -q "tokio" Cargo.toml; then
                # Try to build with cargo
                if cargo check &> "$TEST_OUTPUT_DIR/cargo_check_grpc.log"; then
                    if cargo build &> "$TEST_OUTPUT_DIR/cargo_build_grpc.log"; then
                        test_pass "$test_name"
                        return 0
                    else
                        test_fail "$test_name" "Cargo build failed"
                        cat "$TEST_OUTPUT_DIR/cargo_build_grpc.log" | tail -20
                    fi
                else
                    test_fail "$test_name" "Cargo check failed"
                    cat "$TEST_OUTPUT_DIR/cargo_check_grpc.log" | tail -20
                fi
            else
                test_fail "$test_name" "Missing tonic/tokio dependencies in Cargo.toml"
            fi
        else
            test_fail "$test_name" "Output directory not found: $output_dir"
        fi
    else
        test_fail "$test_name" "Buck2 build failed"
        cat "$TEST_OUTPUT_DIR/build_grpc.log" | tail -20
    fi
    
    return 1
}

# Test: Rust serde integration
test_rust_serde_integration() {
    local test_name="Rust Serde Integration"
    log_info "Running test: $test_name"
    
    # Build the advanced Rust library with serde
    cd "$PROJECT_ROOT"
    if buck2 build //examples/rust:user_rust_advanced &> "$TEST_OUTPUT_DIR/build_serde.log"; then
        local output_dir="$PROJECT_ROOT/buck-out/gen/examples/rust/user_rust_advanced/rust"
        
        if [[ -d "$output_dir" ]]; then
            cd "$output_dir"
            
            # Check if serde dependencies are present
            if grep -q "serde" Cargo.toml; then
                # Try to build with serde feature
                if cargo check --features serde &> "$TEST_OUTPUT_DIR/cargo_check_serde.log"; then
                    if cargo build --features serde &> "$TEST_OUTPUT_DIR/cargo_build_serde.log"; then
                        test_pass "$test_name"
                        return 0
                    else
                        test_fail "$test_name" "Cargo build with serde failed"
                        cat "$TEST_OUTPUT_DIR/cargo_build_serde.log" | tail -20
                    fi
                else
                    test_fail "$test_name" "Cargo check with serde failed"
                    cat "$TEST_OUTPUT_DIR/cargo_check_serde.log" | tail -20
                fi
            else
                test_fail "$test_name" "Missing serde dependency in Cargo.toml"
            fi
        else
            test_fail "$test_name" "Output directory not found: $output_dir"
        fi
    else
        test_fail "$test_name" "Buck2 build failed"
        cat "$TEST_OUTPUT_DIR/build_serde.log" | tail -20
    fi
    
    return 1
}

# Test: Rust clippy compliance
test_rust_clippy_compliance() {
    local test_name="Rust Clippy Compliance"
    log_info "Running test: $test_name"
    
    # Check if clippy is available
    if ! command -v cargo-clippy &> /dev/null; then
        log_warning "Clippy not available, skipping test"
        return 0
    fi
    
    # Test clippy on the basic messages
    cd "$PROJECT_ROOT"
    if buck2 build //examples/rust:user_rust_messages &> "$TEST_OUTPUT_DIR/build_clippy.log"; then
        local output_dir="$PROJECT_ROOT/buck-out/gen/examples/rust/user_rust_messages/rust"
        
        if [[ -d "$output_dir" ]]; then
            cd "$output_dir"
            
            # Run clippy with strict settings
            if cargo clippy -- -D warnings &> "$TEST_OUTPUT_DIR/clippy_check.log"; then
                test_pass "$test_name"
                return 0
            else
                test_fail "$test_name" "Clippy warnings found"
                cat "$TEST_OUTPUT_DIR/clippy_check.log" | tail -20
            fi
        else
            test_fail "$test_name" "Output directory not found: $output_dir"
        fi
    else
        test_fail "$test_name" "Buck2 build failed"
        cat "$TEST_OUTPUT_DIR/build_clippy.log" | tail -20
    fi
    
    return 1
}

# Test: Rust package structure validation
test_rust_package_structure() {
    local test_name="Rust Package Structure"
    log_info "Running test: $test_name"
    
    # Build the full service library
    cd "$PROJECT_ROOT"
    if buck2 build //examples/rust:user_service_rust_full &> "$TEST_OUTPUT_DIR/build_structure.log"; then
        local output_dir="$PROJECT_ROOT/buck-out/gen/examples/rust/user_service_rust_full/rust"
        
        if [[ -d "$output_dir" ]]; then
            # Check expected file structure
            local required_files=(
                "Cargo.toml"
                "src/lib.rs"
                "build.rs"
            )
            
            local missing_files=()
            for file in "${required_files[@]}"; do
                if [[ ! -f "$output_dir/$file" ]]; then
                    missing_files+=("$file")
                fi
            done
            
            if [[ ${#missing_files[@]} -eq 0 ]]; then
                # Check that lib.rs has proper structure
                if grep -q "pub mod" "$output_dir/src/lib.rs" && grep -q "pub use" "$output_dir/src/lib.rs"; then
                    test_pass "$test_name"
                    return 0
                else
                    test_fail "$test_name" "lib.rs missing proper module structure"
                fi
            else
                test_fail "$test_name" "Missing required files: ${missing_files[*]}"
            fi
        else
            test_fail "$test_name" "Output directory not found: $output_dir"
        fi
    else
        test_fail "$test_name" "Buck2 build failed"
        cat "$TEST_OUTPUT_DIR/build_structure.log" | tail -20
    fi
    
    return 1
}

# Test: Rust dependency resolution
test_rust_dependency_resolution() {
    local test_name="Rust Dependency Resolution"
    log_info "Running test: $test_name"
    
    # Build all Rust targets to test dependency resolution
    cd "$PROJECT_ROOT"
    local targets=(
        "//examples/rust:user_rust_messages"
        "//examples/rust:user_service_rust_grpc"
        "//examples/rust:user_rust_advanced"
        "//examples/rust:user_service_rust_full"
    )
    
    local failed_targets=()
    for target in "${targets[@]}"; do
        if ! buck2 build "$target" &> "$TEST_OUTPUT_DIR/build_${target//\//_}.log"; then
            failed_targets+=("$target")
        fi
    done
    
    if [[ ${#failed_targets[@]} -eq 0 ]]; then
        test_pass "$test_name"
        return 0
    else
        test_fail "$test_name" "Failed to build targets: ${failed_targets[*]}"
    fi
    
    return 1
}

# Main test execution function
run_all_tests() {
    log_info "Starting Rust protobuf integration tests..."
    
    # Setup test environment
    setup_test_environment
    
    # Run all tests
    test_basic_rust_messages
    test_rust_grpc_services  
    test_rust_serde_integration
    test_rust_clippy_compliance
    test_rust_package_structure
    test_rust_dependency_resolution
    
    # Print summary
    echo ""
    log_info "Test Summary:"
    log_info "============="
    log_success "Tests passed: $TESTS_PASSED"
    
    if [[ $TESTS_FAILED -gt 0 ]]; then
        log_error "Tests failed: $TESTS_FAILED"
        echo ""
        log_error "Failed tests:"
        for failed_test in "${FAILED_TESTS[@]}"; do
            log_error "  - $failed_test"
        done
        echo ""
        log_error "Check log files in: $TEST_OUTPUT_DIR"
        exit 1
    else
        echo ""
        log_success "🎉 All Rust protobuf tests passed!"
        exit 0
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test artifacts..."
    # Clean up any temporary files if needed
}

# Set up trap for cleanup
trap cleanup EXIT

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run_all_tests "$@"
fi
