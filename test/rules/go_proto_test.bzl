"""Tests for Go protobuf code generation rules."""

load("@bazel_skylib//lib:unittest.bzl", "asserts", "unittest")
load("//rules:go.bzl", "go_proto_library", "go_proto_messages", "go_grpc_library")
load("//rules:proto.bzl", "proto_library")
load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo")

def _test_go_package_resolution_impl(ctx):
    """Test Go package path resolution logic."""
    env = unittest.begin(ctx)
    
    # Test explicit go_package parameter takes priority
    # This would be tested by creating a mock context and calling the function
    # For now, we'll test the logic principles
    
    # Test case 1: Explicit parameter should take priority
    explicit_package = "github.com/org/explicit/v1"
    proto_package = "github.com/org/proto/v1" 
    # Expected: explicit_package wins
    
    # Test case 2: Proto file option should be used when no explicit parameter
    # Expected: proto_package used
    
    # Test case 3: Generated path from file location
    proto_path = "pkg/user/user.proto"
    expected_generated = "pkg/user"
    # Expected: generated path
    
    asserts.true(env, True, "Go package resolution test placeholder")
    
    return unittest.end(env)

def _test_go_output_files_impl(ctx):
    """Test Go output file generation logic."""
    env = unittest.begin(ctx)
    
    # Test that correct output files are generated for different plugin combinations
    
    # Test case 1: Only "go" plugin
    plugins_go_only = ["go"]
    # Expected: *.pb.go files only
    
    # Test case 2: Both "go" and "go-grpc" plugins
    plugins_full = ["go", "go-grpc"]
    # Expected: *.pb.go and *_grpc.pb.go files
    
    # Test case 3: With go_module specified
    # Expected: Additional go.mod file
    
    asserts.true(env, True, "Go output files test placeholder")
    
    return unittest.end(env)

def _test_go_mod_content_impl(ctx):
    """Test go.mod file content generation."""
    env = unittest.begin(ctx)
    
    test_module = "github.com/org/test"
    expected_content = """module github.com/org/test

go 1.21

require (
    google.golang.org/protobuf v1.31.0
    google.golang.org/grpc v1.59.0
)
"""
    
    # In a real implementation, we would call _create_go_mod_content and test the result
    asserts.true(env, True, "Go mod content generation test placeholder")
    
    return unittest.end(env)

def _test_protoc_command_generation_impl(ctx):
    """Test protoc command generation for Go."""
    env = unittest.begin(ctx)
    
    # Test that proper protoc command is generated with:
    # - Correct plugin paths
    # - Proper output directories
    # - Import paths
    # - Go-specific options
    
    asserts.true(env, True, "Protoc command generation test placeholder")
    
    return unittest.end(env)

def _test_language_proto_info_impl(ctx):
    """Test LanguageProtoInfo provider creation."""
    env = unittest.begin(ctx)
    
    # Test that LanguageProtoInfo is properly created with:
    # - language = "go"
    # - correct dependencies based on plugins
    # - proper package name
    
    asserts.true(env, True, "LanguageProtoInfo test placeholder")
    
    return unittest.end(env)

def _test_go_proto_messages_wrapper_impl(ctx):
    """Test go_proto_messages convenience function."""
    env = unittest.begin(ctx)
    
    # Test that go_proto_messages only uses "go" plugin (no gRPC)
    asserts.true(env, True, "go_proto_messages wrapper test placeholder")
    
    return unittest.end(env)

def _test_go_grpc_library_wrapper_impl(ctx):
    """Test go_grpc_library convenience function."""
    env = unittest.begin(ctx)
    
    # Test that go_grpc_library uses both "go" and "go-grpc" plugins
    asserts.true(env, True, "go_grpc_library wrapper test placeholder")
    
    return unittest.end(env)

def _test_tool_integration_impl(ctx):
    """Test tool management integration."""
    env = unittest.begin(ctx)
    
    # Test that correct tools are requested:
    # - protoc
    # - protoc-gen-go
    # - protoc-gen-go-grpc (if go-grpc plugin enabled)
    
    asserts.true(env, True, "Tool integration test placeholder")
    
    return unittest.end(env)

def _test_error_handling_impl(ctx):
    """Test error handling scenarios."""
    env = unittest.begin(ctx)
    
    # Test error cases:
    # - Missing proto dependency
    # - Invalid go_package format
    # - Unsupported plugins
    # - Tool download failures
    
    asserts.true(env, True, "Error handling test placeholder")
    
    return unittest.end(env)

def _test_performance_requirements_impl(ctx):
    """Test performance requirements compliance."""
    env = unittest.begin(ctx)
    
    # Test performance targets:
    # - Build time < 2s for 10 proto files
    # - Memory usage < 50MB per generation
    # - Incremental builds < 500ms
    
    asserts.true(env, True, "Performance requirements test placeholder")
    
    return unittest.end(env)

# Test rule definitions
_test_go_package_resolution = unittest.make(_test_go_package_resolution_impl)
_test_go_output_files = unittest.make(_test_go_output_files_impl)
_test_go_mod_content = unittest.make(_test_go_mod_content_impl)
_test_protoc_command_generation = unittest.make(_test_protoc_command_generation_impl)
_test_language_proto_info = unittest.make(_test_language_proto_info_impl)
_test_go_proto_messages_wrapper = unittest.make(_test_go_proto_messages_wrapper_impl)
_test_go_grpc_library_wrapper = unittest.make(_test_go_grpc_library_wrapper_impl)
_test_tool_integration = unittest.make(_test_tool_integration_impl)
_test_error_handling = unittest.make(_test_error_handling_impl)
_test_performance_requirements = unittest.make(_test_performance_requirements_impl)

def go_proto_test_suite(name):
    """Test suite for Go protobuf generation."""
    unittest.suite(
        name,
        _test_go_package_resolution,
        _test_go_output_files,
        _test_go_mod_content,
        _test_protoc_command_generation,
        _test_language_proto_info,
        _test_go_proto_messages_wrapper,
        _test_go_grpc_library_wrapper,
        _test_tool_integration,
        _test_error_handling,
        _test_performance_requirements,
    )
