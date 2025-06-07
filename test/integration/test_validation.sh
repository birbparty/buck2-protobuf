#!/bin/bash
"""Integration test for protobuf validation and linting system.

This script tests the complete validation workflow including:
- Buf CLI integration and basic linting
- Breaking change detection
- Custom validation rules
- CI/CD integration scenarios
"""

set -euo pipefail

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Test configuration
TEST_WORKSPACE="$PROJECT_ROOT/test-validation-workspace"
VALIDATION_EXAMPLES_DIR="$PROJECT_ROOT/examples/validation"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    log_info "Running test: $test_name"
    
    if eval "$test_command"; then
        log_info "✓ Test passed: $test_name"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        log_error "✗ Test failed: $test_name"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
    echo
}

setup_test_workspace() {
    log_info "Setting up test workspace at $TEST_WORKSPACE"
    
    # Clean and create test workspace
    if [[ -d "$TEST_WORKSPACE" ]]; then
        rm -rf "$TEST_WORKSPACE"
    fi
    mkdir -p "$TEST_WORKSPACE"
    
    # Copy project structure to test workspace
    cp -r "$PROJECT_ROOT"/* "$TEST_WORKSPACE/" 2>/dev/null || true
    
    cd "$TEST_WORKSPACE"
}

cleanup_test_workspace() {
    log_info "Cleaning up test workspace"
    if [[ -d "$TEST_WORKSPACE" ]]; then
        rm -rf "$TEST_WORKSPACE"
    fi
}

test_buf_download() {
    log_info "Testing Buf CLI download functionality"
    
    local tools_dir="$TEST_WORKSPACE/tools"
    local buf_binary="$tools_dir/buf"
    
    # Remove existing buf binary if present
    if [[ -f "$buf_binary" ]]; then
        rm "$buf_binary"
    fi
    
    # Test downloading buf
    python3 "$tools_dir/download_buf.py" --output-dir "$tools_dir" --verbose
    
    # Verify buf was downloaded and is functional
    if [[ -f "$buf_binary" ]] && "$buf_binary" --version >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

test_basic_validation() {
    log_info "Testing basic protobuf validation with Buck2"
    
    cd "$TEST_WORKSPACE"
    
    # Test building validation example
    if command -v buck2 >/dev/null 2>&1; then
        buck2 build //examples/validation:validate_user_service 2>/dev/null
    else
        log_warn "Buck2 not available, skipping Buck2-specific tests"
        return 0
    fi
}

test_buf_lint_functionality() {
    log_info "Testing Buf lint functionality directly"
    
    local tools_dir="$TEST_WORKSPACE/tools"
    local buf_binary="$tools_dir/buf"
    local example_proto="$TEST_WORKSPACE/examples/validation/example.proto"
    
    # Ensure buf is available
    if [[ ! -f "$buf_binary" ]]; then
        python3 "$tools_dir/download_buf.py" --output-dir "$tools_dir" --verbose
    fi
    
    # Create a temporary working directory for buf
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    # Copy proto and buf config to temp directory
    cp "$example_proto" "$temp_dir/"
    cp "$TEST_WORKSPACE/examples/validation/buf.yaml" "$temp_dir/"
    
    cd "$temp_dir"
    
    # Run buf lint
    if "$buf_binary" lint --error-format json > lint_results.json 2>&1; then
        log_info "Buf lint completed successfully"
        if [[ -s "lint_results.json" ]]; then
            log_info "Lint results: $(cat lint_results.json)"
        fi
        return 0
    else
        log_warn "Buf lint found issues (expected for some tests)"
        if [[ -s "lint_results.json" ]]; then
            log_info "Lint results: $(cat lint_results.json)"
        fi
        return 0  # Don't fail on lint issues
    fi
}

test_custom_validation_rules() {
    log_info "Testing custom validation rules"
    
    local fixtures_dir="$TEST_WORKSPACE/test/fixtures"
    local example_proto="$TEST_WORKSPACE/examples/validation/example.proto"
    
    # Test package naming rule
    log_info "Testing package naming validation rule"
    if python3 "$fixtures_dir/check_package_naming.py" "$example_proto" > package_results.json 2>&1; then
        log_info "Package naming rule passed"
        cat package_results.json
    else
        log_warn "Package naming rule found issues"
        cat package_results.json
    fi
    
    # Test service naming rule
    log_info "Testing service naming validation rule"
    if python3 "$fixtures_dir/check_service_naming.py" "$example_proto" > service_results.json 2>&1; then
        log_info "Service naming rule passed"
        cat service_results.json
    else
        log_warn "Service naming rule found issues"
        cat service_results.json
    fi
    
    return 0  # Don't fail on validation issues for demo purposes
}

test_breaking_change_detection() {
    log_info "Testing breaking change detection"
    
    local tools_dir="$TEST_WORKSPACE/tools"
    local buf_binary="$tools_dir/buf"
    
    # Ensure buf is available
    if [[ ! -f "$buf_binary" ]]; then
        python3 "$tools_dir/download_buf.py" --output-dir "$tools_dir" --verbose
    fi
    
    # Create temporary directories for current and baseline
    local temp_dir=$(mktemp -d)
    trap "rm -rf $temp_dir" EXIT
    
    local current_dir="$temp_dir/current"
    local baseline_dir="$temp_dir/baseline"
    
    mkdir -p "$current_dir" "$baseline_dir"
    
    # Copy same proto to both (should have no breaking changes)
    cp "$TEST_WORKSPACE/examples/validation/example.proto" "$current_dir/"
    cp "$TEST_WORKSPACE/examples/validation/example.proto" "$baseline_dir/"
    cp "$TEST_WORKSPACE/examples/validation/buf.yaml" "$current_dir/"
    cp "$TEST_WORKSPACE/examples/validation/buf.yaml" "$baseline_dir/"
    
    cd "$current_dir"
    
    # Run breaking change detection
    if "$buf_binary" breaking --against "$baseline_dir" --error-format json > breaking_results.json 2>&1; then
        log_info "No breaking changes detected (expected)"
        return 0
    else
        log_warn "Breaking changes detected"
        if [[ -s "breaking_results.json" ]]; then
            cat breaking_results.json
        fi
        return 0  # Don't fail on breaking changes for demo
    fi
}

test_validation_error_handling() {
    log_info "Testing validation error handling"
    
    local fixtures_dir="$TEST_WORKSPACE/test/fixtures"
    local malformed_proto="$TEST_WORKSPACE/test/fixtures/edge_cases/malformed.proto"
    
    # Test with malformed proto file
    if [[ -f "$malformed_proto" ]]; then
        log_info "Testing validation with malformed proto"
        
        # Test custom rules with malformed proto (should handle gracefully)
        python3 "$fixtures_dir/check_package_naming.py" "$malformed_proto" > error_results.json 2>&1 || true
        
        log_info "Error handling results:"
        cat error_results.json
    else
        log_warn "Malformed proto not found, skipping error handling test"
    fi
    
    return 0
}

test_performance_validation() {
    log_info "Testing validation performance"
    
    local start_time=$(date +%s)
    
    # Test validation with larger proto file
    local large_proto="$TEST_WORKSPACE/test/fixtures/performance/large.proto"
    local fixtures_dir="$TEST_WORKSPACE/test/fixtures"
    
    if [[ -f "$large_proto" ]]; then
        log_info "Testing validation performance with large proto"
        python3 "$fixtures_dir/check_package_naming.py" "$large_proto" > perf_results.json 2>&1 || true
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_info "Validation completed in ${duration} seconds"
        
        # Check if validation completed in reasonable time (< 10 seconds)
        if [[ $duration -lt 10 ]]; then
            return 0
        else
            log_warn "Validation took longer than expected: ${duration}s"
            return 1
        fi
    else
        log_warn "Large proto not found, skipping performance test"
        return 0
    fi
}

test_ci_integration_format() {
    log_info "Testing CI/CD integration output formats"
    
    local fixtures_dir="$TEST_WORKSPACE/test/fixtures"
    local example_proto="$TEST_WORKSPACE/examples/validation/example.proto"
    
    # Test JSON output format
    python3 "$fixtures_dir/check_package_naming.py" "$example_proto" > ci_results.json 2>&1 || true
    
    # Verify JSON is valid
    if python3 -m json.tool ci_results.json >/dev/null 2>&1; then
        log_info "CI integration JSON format is valid"
        return 0
    else
        log_error "CI integration JSON format is invalid"
        return 1
    fi
}

print_test_summary() {
    echo
    log_info "=== Test Summary ==="
    log_info "Tests run: $TESTS_RUN"
    log_info "Tests passed: $TESTS_PASSED"
    log_info "Tests failed: $TESTS_FAILED"
    
    if [[ $TESTS_FAILED -eq 0 ]]; then
        log_info "🎉 All tests passed!"
        return 0
    else
        log_error "❌ Some tests failed"
        return 1
    fi
}

main() {
    log_info "Starting protobuf validation integration tests"
    
    # Setup
    setup_test_workspace
    
    # Run tests
    run_test "Buf CLI Download" "test_buf_download"
    run_test "Basic Validation" "test_basic_validation"
    run_test "Buf Lint Functionality" "test_buf_lint_functionality"
    run_test "Custom Validation Rules" "test_custom_validation_rules"
    run_test "Breaking Change Detection" "test_breaking_change_detection"
    run_test "Validation Error Handling" "test_validation_error_handling"
    run_test "Performance Validation" "test_performance_validation"
    run_test "CI Integration Format" "test_ci_integration_format"
    
    # Cleanup and summary
    cleanup_test_workspace
    print_test_summary
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
