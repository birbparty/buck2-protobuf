#!/bin/bash
# Integration test script for C++ protobuf compilation
# Validates that generated C++ code compiles and links correctly

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$TEST_DIR/../.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/buck-out/cpp-integration-test"
TEMP_DIR=$(mktemp -d)

echo -e "${YELLOW}Starting C++ protobuf integration tests...${NC}"
echo "Project root: $PROJECT_ROOT"
echo "Build directory: $BUILD_DIR"
echo "Temp directory: $TEMP_DIR"

cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

# Function to run a test and capture result
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "${YELLOW}Running test: $test_name${NC}"
    
    if eval "$test_command" > "$TEMP_DIR/${test_name}.log" 2>&1; then
        echo -e "${GREEN}✓ PASS: $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL: $test_name${NC}"
        echo "Error output:"
        cat "$TEMP_DIR/${test_name}.log"
        return 1
    fi
}

# Change to project root
cd "$PROJECT_ROOT"

echo -e "${YELLOW}Setting up test environment...${NC}"
mkdir -p "$BUILD_DIR"

# Test 1: Basic C++ protobuf message compilation
run_test "cpp_basic_message_compilation" "
    buck2 build //examples/cpp:user_cpp_proto &&
    test -f buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.h &&
    test -f buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.cc
"

# Test 2: C++ gRPC service compilation
run_test "cpp_grpc_service_compilation" "
    buck2 build //examples/cpp:user_service_cpp_proto &&
    test -f buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/src/user_service.grpc.pb.h &&
    test -f buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/src/user_service.grpc.pb.cc
"

# Test 3: Namespace verification
run_test "cpp_namespace_verification" "
    buck2 build //examples/cpp:user_cpp_proto &&
    grep -q 'namespace user' buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.h &&
    grep -q 'namespace v1' buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.h
"

# Test 4: Build configuration generation
run_test "cpp_build_config_generation" "
    buck2 build //examples/cpp:user_cpp_proto &&
    test -f buck-out/gen/examples/cpp/user_cpp_proto/cpp/BUILD &&
    test -f buck-out/gen/examples/cpp/user_cpp_proto/cpp/CMakeLists.txt &&
    grep -q 'cc_library' buck-out/gen/examples/cpp/user_cpp_proto/cpp/BUILD
"

# Test 5: Compiler standard configuration
run_test "cpp_compiler_standard_config" "
    buck2 build //examples/cpp:user_cpp_advanced &&
    grep -q 'c++20' buck-out/gen/examples/cpp/user_cpp_advanced/cpp/BUILD ||
    grep -q 'CMAKE_CXX_STANDARD 20' buck-out/gen/examples/cpp/user_cpp_advanced/cpp/CMakeLists.txt
"

# Test 6: Performance optimization flags
run_test "cpp_performance_optimization" "
    buck2 build //examples/cpp:user_service_cpp_optimized &&
    grep -q '\-O3' buck-out/gen/examples/cpp/user_service_cpp_optimized/cpp/BUILD &&
    grep -q '\-DNDEBUG' buck-out/gen/examples/cpp/user_service_cpp_optimized/cpp/BUILD
"

# Test 7: Actual C++ compilation with system compiler (if available)
if command -v g++ > /dev/null 2>&1; then
    run_test "cpp_system_compilation" "
        buck2 build //examples/cpp:user_cpp_proto &&
        cd buck-out/gen/examples/cpp/user_cpp_proto/cpp &&
        g++ -std=c++17 -I/usr/local/include -I\$PWD/src -c src/user.pb.cc -o $TEMP_DIR/user.pb.o
    "
else
    echo -e "${YELLOW}Skipping system compilation test (g++ not available)${NC}"
fi

# Test 8: Header inclusion verification
run_test "cpp_header_inclusion" "
    buck2 build //examples/cpp:user_cpp_proto &&
    grep -q '#include.*protobuf' buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.h &&
    grep -q 'google::protobuf' buck-out/gen/examples/cpp/user_cpp_proto/cpp/src/user.pb.h
"

# Test 9: gRPC service method verification
run_test "cpp_grpc_service_methods" "
    buck2 build //examples/cpp:user_service_cpp_proto &&
    grep -q 'GetUser' buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/src/user_service.grpc.pb.h &&
    grep -q 'CreateUser' buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/src/user_service.grpc.pb.h &&
    grep -q 'service UserService' buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/src/user_service.grpc.pb.h
"

# Test 10: Dependency verification in BUILD files
run_test "cpp_dependency_verification" "
    buck2 build //examples/cpp:user_service_cpp_proto &&
    grep -q 'protobuf' buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/BUILD &&
    grep -q 'grpc' buck-out/gen/examples/cpp/user_service_cpp_proto/cpp/BUILD
"

# Test 11: Error handling for invalid proto
run_test "cpp_error_handling" "
    ! buck2 build //test/fixtures/edge_cases:malformed_proto_cpp 2>/dev/null
"

# Test 12: Multiple plugin support
run_test "cpp_multiple_plugins" "
    buck2 build //examples/cpp:user_service_cpp_optimized &&
    test -f buck-out/gen/examples/cpp/user_service_cpp_optimized/cpp/src/user_service.pb.h &&
    test -f buck-out/gen/examples/cpp/user_service_cpp_optimized/cpp/src/user_service.grpc.pb.h
"

echo -e "${GREEN}All C++ protobuf integration tests completed!${NC}"

# Generate summary report
echo -e "${YELLOW}Test Summary:${NC}"
echo "- Basic message compilation: ✓"
echo "- gRPC service compilation: ✓"
echo "- Namespace verification: ✓"
echo "- Build configuration: ✓"
echo "- Compiler standards: ✓"
echo "- Performance optimization: ✓"
echo "- Header inclusion: ✓"
echo "- Service methods: ✓"
echo "- Dependencies: ✓"
echo "- Error handling: ✓"
echo "- Multiple plugins: ✓"

if command -v g++ > /dev/null 2>&1; then
    echo "- System compilation: ✓"
else
    echo "- System compilation: (skipped - compiler not available)"
fi

echo -e "${GREEN}C++ protobuf integration test suite: PASSED${NC}"
