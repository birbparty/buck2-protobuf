#!/bin/bash

# Integration test script for Go protobuf code generation and compilation
# This script tests that generated Go code compiles successfully with the Go toolchain

set -euo pipefail

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TEST_DIR="${SCRIPT_DIR}/go_compilation_test"
GO_VERSION="1.21"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Go is installed
    if ! command -v go &> /dev/null; then
        log_error "Go toolchain not found. Please install Go ${GO_VERSION} or later."
        exit 1
    fi
    
    # Check Go version
    GO_INSTALLED_VERSION=$(go version | grep -oE '[0-9]+\.[0-9]+' | head -n1)
    log_info "Found Go version: ${GO_INSTALLED_VERSION}"
    
    # Check if Buck2 is available (for actual build testing)
    if command -v buck2 &> /dev/null; then
        log_info "Buck2 found: $(buck2 --version)"
    else
        log_warning "Buck2 not found. Skipping Buck2 build tests."
    fi
}

# Setup test environment
setup_test_env() {
    log_info "Setting up test environment..."
    
    # Clean and create test directory
    rm -rf "${TEST_DIR}"
    mkdir -p "${TEST_DIR}"
    cd "${TEST_DIR}"
    
    # Initialize Go module for testing
    go mod init go-proto-test
    
    # Add required dependencies
    log_info "Adding Go protobuf dependencies..."
    go get google.golang.org/protobuf@v1.31.0
    go get google.golang.org/grpc@v1.59.0
}

# Test basic protobuf message compilation
test_basic_protobuf_compilation() {
    log_info "Testing basic protobuf message compilation..."
    
    # Create a simple proto file
    cat > user.proto << 'EOF'
syntax = "proto3";

package user.v1;

option go_package = "go-proto-test/user/v1";

message User {
  int64 id = 1;
  string name = 2;
  string email = 3;
}

message CreateUserRequest {
  string name = 1;
  string email = 2;
}
EOF

    # Generate Go code using protoc directly (simulating our Buck2 rule)
    log_info "Generating Go code with protoc..."
    
    # Check if protoc is available
    if ! command -v protoc &> /dev/null; then
        log_warning "protoc not found. Downloading protoc for testing..."
        # In a real scenario, our Buck2 rule would handle this
        curl -L -o protoc.zip "https://github.com/protocolbuffers/protobuf/releases/download/v24.4/protoc-24.4-linux-x86_64.zip"
        unzip -q protoc.zip
        export PATH="${PWD}/bin:${PATH}"
    fi
    
    # Install protoc-gen-go if not available
    if ! command -v protoc-gen-go &> /dev/null; then
        log_info "Installing protoc-gen-go..."
        go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.31.0
    fi
    
    # Generate Go code
    mkdir -p user/v1
    protoc --go_out=. --go_opt=paths=source_relative user.proto
    
    # Test Go compilation
    log_info "Testing Go code compilation..."
    cat > main.go << 'EOF'
package main

import (
    "fmt"
    "go-proto-test/user/v1"
)

func main() {
    user := &user.User{
        Id:    1,
        Name:  "Test User",
        Email: "test@example.com",
    }
    
    req := &user.CreateUserRequest{
        Name:  user.Name,
        Email: user.Email,
    }
    
    fmt.Printf("User: %+v\n", user)
    fmt.Printf("Request: %+v\n", req)
}
EOF

    # Compile and run
    if go run main.go > /dev/null 2>&1; then
        log_success "Basic protobuf compilation test passed"
        return 0
    else
        log_error "Basic protobuf compilation test failed"
        return 1
    fi
}

# Test gRPC service compilation
test_grpc_compilation() {
    log_info "Testing gRPC service compilation..."
    
    # Create service proto file
    cat > user_service.proto << 'EOF'
syntax = "proto3";

package user.service.v1;

import "user.proto";

option go_package = "go-proto-test/user/service/v1";

service UserService {
  rpc CreateUser(user.v1.CreateUserRequest) returns (user.v1.User);
  rpc GetUser(GetUserRequest) returns (user.v1.User);
  rpc ListUsers(ListUsersRequest) returns (stream user.v1.User);
}

message GetUserRequest {
  int64 id = 1;
}

message ListUsersRequest {
  int32 limit = 1;
}
EOF

    # Install protoc-gen-go-grpc if not available
    if ! command -v protoc-gen-go-grpc &> /dev/null; then
        log_info "Installing protoc-gen-go-grpc..."
        go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.3.0
    fi
    
    # Generate gRPC code
    mkdir -p user/service/v1
    protoc --go_out=. --go_opt=paths=source_relative \
           --go-grpc_out=. --go-grpc_opt=paths=source_relative \
           --proto_path=. user_service.proto
    
    # Test gRPC compilation
    log_info "Testing gRPC code compilation..."
    cat > grpc_test.go << 'EOF'
package main

import (
    "context"
    "fmt"
    "go-proto-test/user/v1"
    "go-proto-test/user/service/v1"
    "google.golang.org/grpc"
)

type userServer struct {
    service.UnimplementedUserServiceServer
}

func (s *userServer) CreateUser(ctx context.Context, req *user.CreateUserRequest) (*user.User, error) {
    return &user.User{
        Id:    1,
        Name:  req.Name,
        Email: req.Email,
    }, nil
}

func (s *userServer) GetUser(ctx context.Context, req *service.GetUserRequest) (*user.User, error) {
    return &user.User{
        Id:    req.Id,
        Name:  "Test User",
        Email: "test@example.com",
    }, nil
}

func main() {
    server := &userServer{}
    _ = grpc.NewServer()
    
    fmt.Printf("gRPC server type: %T\n", server)
}
EOF

    # Compile gRPC test
    if go build -o grpc_test grpc_test.go > /dev/null 2>&1; then
        log_success "gRPC compilation test passed"
        return 0
    else
        log_error "gRPC compilation test failed"
        go build grpc_test.go 2>&1 | head -20  # Show compilation errors
        return 1
    fi
}

# Test performance requirements
test_performance() {
    log_info "Testing performance requirements..."
    
    # Create multiple proto files to test compilation time
    for i in {1..10}; do
        cat > "proto_${i}.proto" << EOF
syntax = "proto3";

package test.v${i};

option go_package = "go-proto-test/test/v${i}";

message TestMessage${i} {
  int64 id = 1;
  string name = 2;
  repeated string tags = 3;
}

message TestRequest${i} {
  TestMessage${i} message = 1;
  int32 limit = 2;
}
EOF
    done
    
    # Time the compilation
    log_info "Timing compilation of 10 proto files..."
    start_time=$(date +%s.%N)
    
    for i in {1..10}; do
        mkdir -p "test/v${i}"
        protoc --go_out=. --go_opt=paths=source_relative "proto_${i}.proto" || {
            log_error "Failed to compile proto_${i}.proto"
            return 1
        }
    done
    
    end_time=$(date +%s.%N)
    compilation_time=$(echo "$end_time - $start_time" | bc -l)
    
    log_info "Compilation time: ${compilation_time} seconds"
    
    # Check if within performance target (< 2 seconds)
    if (( $(echo "$compilation_time < 2.0" | bc -l) )); then
        log_success "Performance test passed: ${compilation_time}s < 2.0s target"
        return 0
    else
        log_warning "Performance test warning: ${compilation_time}s >= 2.0s target"
        return 1
    fi
}

# Test go.mod integration
test_go_mod_integration() {
    log_info "Testing go.mod integration..."
    
    # Create a go.mod file similar to what our rule would generate
    cat > test_module/go.mod << 'EOF'
module github.com/org/test

go 1.21

require (
    google.golang.org/protobuf v1.31.0
    google.golang.org/grpc v1.59.0
)
EOF

    mkdir -p test_module
    cd test_module
    
    # Copy generated proto files
    cp -r ../user .
    
    # Test that go mod tidy works
    if go mod tidy > /dev/null 2>&1; then
        log_success "go.mod integration test passed"
        cd ..
        return 0
    else
        log_error "go.mod integration test failed"
        cd ..
        return 1
    fi
}

# Test package resolution
test_package_resolution() {
    log_info "Testing Go package resolution..."
    
    # Test different package resolution scenarios
    
    # Test 1: Explicit go_package option in proto
    cat > explicit_package.proto << 'EOF'
syntax = "proto3";

package explicit.test;

option go_package = "go-proto-test/explicit/v1";

message ExplicitMessage {
  string value = 1;
}
EOF

    mkdir -p explicit/v1
    protoc --go_out=. --go_opt=paths=source_relative explicit_package.proto
    
    # Verify the package declaration
    if grep -q "package v1" explicit/v1/explicit_package.pb.go; then
        log_success "Explicit package resolution test passed"
    else
        log_error "Explicit package resolution test failed"
        return 1
    fi
    
    # Test 2: Generated package path from file location
    mkdir -p generated/path
    cat > generated/path/path_test.proto << 'EOF'
syntax = "proto3";

package path.test;

message PathMessage {
  string value = 1;
}
EOF

    protoc --go_out=. --go_opt=paths=source_relative generated/path/path_test.proto
    
    if [ -f "generated/path/path_test.pb.go" ]; then
        log_success "Generated package path test passed"
    else
        log_error "Generated package path test failed"
        return 1
    fi
    
    return 0
}

# Run all tests
run_all_tests() {
    log_info "Starting Go protobuf compilation tests..."
    
    local failed_tests=0
    
    check_prerequisites || exit 1
    setup_test_env || exit 1
    
    # Run individual tests
    test_basic_protobuf_compilation || ((failed_tests++))
    test_grpc_compilation || ((failed_tests++))
    test_performance || ((failed_tests++))
    test_go_mod_integration || ((failed_tests++))
    test_package_resolution || ((failed_tests++))
    
    # Summary
    log_info "Test Summary:"
    if [ $failed_tests -eq 0 ]; then
        log_success "All tests passed! ✅"
        log_success "Generated Go code compiles successfully with Go toolchain"
        log_success "gRPC services generate correct client/server stubs"
        log_success "Performance targets met for build times"
        log_success "Go module integration works correctly"
    else
        log_error "$failed_tests test(s) failed ❌"
        exit 1
    fi
}

# Cleanup function
cleanup() {
    if [ -d "${TEST_DIR}" ]; then
        log_info "Cleaning up test environment..."
        rm -rf "${TEST_DIR}"
    fi
}

# Trap cleanup on exit
trap cleanup EXIT

# Main execution
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    run_all_tests
fi
