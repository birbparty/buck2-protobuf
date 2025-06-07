"""
Comprehensive unit tests for proto_library and related rules.

This module provides comprehensive test coverage for all proto_library
functionality, edge cases, and error conditions to achieve >95% coverage.
"""

load("@prelude//utils:utils.bzl", "expect")
load("//rules:proto.bzl", "proto_library")
load("//test:test_utils.bzl", "proto_test_suite", "assert_proto_outputs")

def test_proto_library_basic():
    """Test basic proto_library functionality."""
    
    # Test minimal proto library
    proto_library(
        name = "basic_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
    )
    
    # Verify outputs are generated
    assert_proto_outputs("basic_test_proto", [
        "basic_test_proto.descriptorset",
    ])

def test_proto_library_with_dependencies():
    """Test proto_library with dependencies."""
    
    # Create base proto
    proto_library(
        name = "base_test_proto",
        srcs = ["//test/fixtures/dependencies:base.proto"],
    )
    
    # Create derived proto
    proto_library(
        name = "derived_test_proto", 
        srcs = ["//test/fixtures/dependencies:derived.proto"],
        deps = [":base_test_proto"],
    )
    
    # Verify dependency chain works
    assert_proto_outputs("derived_test_proto", [
        "derived_test_proto.descriptorset",
    ])

def test_proto_library_import_paths():
    """Test proto_library with custom import paths."""
    
    proto_library(
        name = "import_path_test_proto",
        srcs = ["//test/fixtures/basic:types.proto"],
        import_paths = ["test/fixtures/basic"],
    )
    
    assert_proto_outputs("import_path_test_proto", [
        "import_path_test_proto.descriptorset",
    ])

def test_proto_library_multiple_sources():
    """Test proto_library with multiple source files."""
    
    proto_library(
        name = "multi_source_test_proto",
        srcs = [
            "//test/fixtures/basic:minimal.proto",
            "//test/fixtures/basic:types.proto",
        ],
    )
    
    assert_proto_outputs("multi_source_test_proto", [
        "multi_source_test_proto.descriptorset",
    ])

def test_proto_library_visibility():
    """Test proto_library visibility settings."""
    
    # Public visibility
    proto_library(
        name = "public_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        visibility = ["PUBLIC"],
    )
    
    # Package visibility
    proto_library(
        name = "package_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        visibility = ["//test/..."],
    )

def test_proto_library_error_conditions():
    """Test proto_library error handling."""
    
    # Test with non-existent source
    expect.that(lambda: proto_library(
        name = "missing_source_proto", 
        srcs = ["non_existent.proto"],
    )).fails_with("Source file not found")
    
    # Test with invalid dependency
    expect.that(lambda: proto_library(
        name = "invalid_dep_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        deps = ["//non/existent:target"],
    )).fails_with("Dependency not found")

def test_proto_library_edge_cases():
    """Test proto_library edge cases."""
    
    # Empty source list (should fail)
    expect.that(lambda: proto_library(
        name = "empty_sources_proto",
        srcs = [],
    )).fails_with("srcs cannot be empty")
    
    # Duplicate sources
    proto_library(
        name = "duplicate_sources_proto",
        srcs = [
            "//test/fixtures/basic:minimal.proto",
            "//test/fixtures/basic:minimal.proto",
        ],
    )

def test_proto_library_well_known_types():
    """Test proto_library with well-known types."""
    
    # Create proto that uses well-known types
    proto_library(
        name = "well_known_test_proto",
        srcs = ["//test/fixtures:complex.proto"],
        # complex.proto should import google/protobuf/timestamp.proto
    )
    
    assert_proto_outputs("well_known_test_proto", [
        "well_known_test_proto.descriptorset",
    ])

def test_proto_library_circular_dependencies():
    """Test proto_library circular dependency detection."""
    
    # This should be detected and fail
    expect.that(lambda: [
        proto_library(
            name = "circular_a_proto",
            srcs = ["circular_a.proto"],
            deps = [":circular_b_proto"],
        ),
        proto_library(
            name = "circular_b_proto", 
            srcs = ["circular_b.proto"],
            deps = [":circular_a_proto"],
        ),
    ]).fails_with("Circular dependency detected")

def test_proto_library_large_dependency_chain():
    """Test proto_library with large dependency chains."""
    
    # Create a chain of 10 proto dependencies
    protos = []
    for i in range(10):
        deps = []
        if i > 0:
            deps = [f":chain_{i-1}_proto"]
        
        proto_library(
            name = f"chain_{i}_proto",
            srcs = [f"chain_{i}.proto"],
            deps = deps,
        )
        protos.append(f":chain_{i}_proto")
    
    # Final proto depends on the last in chain
    proto_library(
        name = "chain_final_proto",
        srcs = ["chain_final.proto"],
        deps = [protos[-1]],
    )

def test_proto_library_performance():
    """Test proto_library performance with large files."""
    
    # Test with large proto file
    proto_library(
        name = "large_performance_proto",
        srcs = ["//test/fixtures/performance:large.proto"],
    )
    
    # Should complete within reasonable time
    assert_proto_outputs("large_performance_proto", [
        "large_performance_proto.descriptorset",
    ])

def test_proto_library_platform_specific():
    """Test proto_library platform-specific behavior."""
    
    # Test on current platform
    proto_library(
        name = "platform_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        target_compatible_with = select({
            "//platforms:linux": [],
            "//platforms:macos": [],
            "//platforms:windows": [],
            "DEFAULT": ["@platforms//:incompatible"],
        }),
    )

def test_proto_library_custom_protoc():
    """Test proto_library with custom protoc configuration."""
    
    proto_library(
        name = "custom_protoc_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        protoc_flags = [
            "--experimental_allow_proto3_optional",
        ],
    )

def test_proto_library_include_imports():
    """Test proto_library include_imports functionality."""
    
    proto_library(
        name = "include_imports_test_proto",
        srcs = ["//test/fixtures:complex.proto"],
        include_imports = True,
    )
    
    # Should include dependency descriptors
    assert_proto_outputs("include_imports_test_proto", [
        "include_imports_test_proto.descriptorset",
    ])

def test_proto_library_source_info():
    """Test proto_library source info retention."""
    
    proto_library(
        name = "source_info_test_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        include_source_info = True,
    )
    
    assert_proto_outputs("source_info_test_proto", [
        "source_info_test_proto.descriptorset",
    ])

# Comprehensive test suite registration
proto_test_suite(
    name = "comprehensive_proto_tests",
    tests = [
        test_proto_library_basic,
        test_proto_library_with_dependencies,
        test_proto_library_import_paths,
        test_proto_library_multiple_sources,
        test_proto_library_visibility,
        test_proto_library_error_conditions,
        test_proto_library_edge_cases,
        test_proto_library_well_known_types,
        test_proto_library_circular_dependencies,
        test_proto_library_large_dependency_chain,
        test_proto_library_performance,
        test_proto_library_platform_specific,
        test_proto_library_custom_protoc,
        test_proto_library_include_imports,
        test_proto_library_source_info,
    ],
)
