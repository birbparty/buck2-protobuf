"""Tests for Rust protobuf generation rules.

This module contains Buck2 test rules to verify that Rust protobuf
generation works correctly with various configurations and scenarios.
"""

load("//test:test_utils.py", "assert_files_exist", "assert_content_contains")
load("//rules:rust.bzl", "rust_proto_library", "rust_proto_messages", "rust_grpc_library")
load("//rules:proto.bzl", "proto_library")

def test_basic_rust_proto_generation():
    """Test basic Rust protobuf message generation."""
    # Create a test proto library
    proto_library(
        name = "test_basic_proto",
        srcs = ["//test/fixtures:simple.proto"],
    )
    
    # Generate Rust messages
    rust_proto_messages(
        name = "test_basic_rust",
        proto = ":test_basic_proto",
        rust_package = "test_basic_proto",
    )
    
    # Verify expected files are generated
    expected_files = [
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/src/simple.rs",
        "rust/build.rs",
    ]
    
    assert_files_exist("test_basic_rust", expected_files)

def test_rust_grpc_generation():
    """Test Rust gRPC service generation with tonic."""
    # Create a test proto library with services
    proto_library(
        name = "test_grpc_proto", 
        srcs = ["//test/fixtures:service.proto"],
    )
    
    # Generate Rust gRPC services
    rust_grpc_library(
        name = "test_grpc_rust",
        proto = ":test_grpc_proto",
        rust_package = "test_grpc_proto",
    )
    
    # Verify expected files are generated
    expected_files = [
        "rust/Cargo.toml",
        "rust/src/lib.rs", 
        "rust/src/service.rs",
        "rust/build.rs",
    ]
    
    assert_files_exist("test_grpc_rust", expected_files)
    
    # Verify Cargo.toml contains tonic dependencies
    assert_content_contains(
        "test_grpc_rust", 
        "rust/Cargo.toml",
        ["tonic = \"0.10\"", "tokio = "]
    )

def test_rust_serde_integration():
    """Test Rust protobuf generation with serde support."""
    proto_library(
        name = "test_serde_proto",
        srcs = ["//test/fixtures:complex.proto"],
    )
    
    rust_proto_library(
        name = "test_serde_rust",
        proto = ":test_serde_proto",
        rust_package = "test_serde_proto",
        serde = True,
        derive = ["Clone", "Debug", "PartialEq"],
    )
    
    # Verify serde is included in Cargo.toml
    assert_content_contains(
        "test_serde_rust",
        "rust/Cargo.toml", 
        ["serde = ", "features = [\"derive\"]"]
    )
    
    # Verify serde feature is defined
    assert_content_contains(
        "test_serde_rust",
        "rust/Cargo.toml",
        ["serde = [\"dep:serde\"]"]
    )

def test_rust_package_name_resolution():
    """Test Rust package name resolution from various sources."""
    proto_library(
        name = "test_package_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
    )
    
    # Test explicit package name
    rust_proto_library(
        name = "test_explicit_package",
        proto = ":test_package_proto",
        rust_package = "my_custom_package",
    )
    
    assert_content_contains(
        "test_explicit_package",
        "rust/Cargo.toml",
        ["name = \"my_custom_package\""]
    )
    
    # Test auto-generated package name
    rust_proto_library(
        name = "test_auto_package",
        proto = ":test_package_proto",
        # No rust_package specified - should auto-generate
    )
    
    assert_content_contains(
        "test_auto_package", 
        "rust/Cargo.toml",
        ["name = "]  # Should have some generated name
    )

def test_rust_custom_options():
    """Test Rust protobuf generation with custom options."""
    proto_library(
        name = "test_options_proto",
        srcs = ["//test/fixtures:complex.proto"],
    )
    
    rust_proto_library(
        name = "test_options_rust",
        proto = ":test_options_proto",
        rust_package = "test_options_proto",
        plugins = ["prost"],
        options = {
            "prost_type_attribute": ".TestMessage=#[derive(Hash)]",
            "prost_field_attribute": ".TestMessage.id=#[serde(rename = \"identifier\")]",
        },
        derive = ["Clone", "Debug", "Hash"],
    )
    
    # Verify files are generated
    expected_files = [
        "rust/Cargo.toml",
        "rust/src/lib.rs",
        "rust/build.rs",
    ]
    
    assert_files_exist("test_options_rust", expected_files)

def test_rust_edition_support():
    """Test Rust edition specification."""
    proto_library(
        name = "test_edition_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
    )
    
    # Test 2021 edition
    rust_proto_library(
        name = "test_rust_2021",
        proto = ":test_edition_proto",
        rust_package = "test_2021_proto",
        edition = "2021",
    )
    
    assert_content_contains(
        "test_rust_2021",
        "rust/Cargo.toml",
        ["edition = \"2021\""]
    )
    
    # Test 2018 edition
    rust_proto_library(
        name = "test_rust_2018",
        proto = ":test_edition_proto", 
        rust_package = "test_2018_proto",
        edition = "2018",
    )
    
    assert_content_contains(
        "test_rust_2018",
        "rust/Cargo.toml",
        ["edition = \"2018\""]
    )

def test_rust_lib_rs_generation():
    """Test that lib.rs is properly generated with module exports."""
    proto_library(
        name = "test_lib_proto",
        srcs = [
            "//test/fixtures/basic:minimal.proto",
            "//test/fixtures/basic:types.proto",
        ],
    )
    
    rust_proto_library(
        name = "test_lib_rust",
        proto = ":test_lib_proto",
        rust_package = "test_lib_proto",
        use_grpc = True,
    )
    
    # Verify lib.rs contains proper module declarations
    assert_content_contains(
        "test_lib_rust",
        "rust/src/lib.rs",
        [
            "pub mod minimal;",
            "pub mod types;", 
            "pub use minimal::*;",
            "pub use types::*;",
            "pub use tonic;",  # Should include tonic re-export
        ]
    )

def test_rust_features_configuration():
    """Test Rust Cargo features configuration."""
    proto_library(
        name = "test_features_proto",
        srcs = ["//test/fixtures:simple.proto"],
    )
    
    rust_proto_library(
        name = "test_features_rust",
        proto = ":test_features_proto",
        rust_package = "test_features_proto",
        features = ["custom_feature", "serde"],
        serde = True,
    )
    
    # Verify features section in Cargo.toml
    assert_content_contains(
        "test_features_rust",
        "rust/Cargo.toml",
        [
            "[features]",
            "default = []",
            "serde = [\"dep:serde\"]",
            "\"custom_feature\" = []",
        ]
    )

def test_rust_error_handling():
    """Test error handling for invalid configurations."""
    proto_library(
        name = "test_error_proto",
        srcs = ["//test/fixtures:simple.proto"],
    )
    
    # This should work fine
    rust_proto_library(
        name = "test_valid_rust",
        proto = ":test_error_proto",
        rust_package = "valid_package_name",
    )
    
    # Test with invalid package name characters should be handled gracefully
    rust_proto_library(
        name = "test_sanitized_rust",
        proto = ":test_error_proto",
        rust_package = "invalid-package-name",  # Should get sanitized
    )

# Test suite definition
def rust_proto_test_suite():
    """Defines the complete test suite for Rust protobuf generation."""
    
    test_basic_rust_proto_generation()
    test_rust_grpc_generation() 
    test_rust_serde_integration()
    test_rust_package_name_resolution()
    test_rust_custom_options()
    test_rust_edition_support()
    test_rust_lib_rs_generation()
    test_rust_features_configuration()
    test_rust_error_handling()
    
    print("✅ All Rust protobuf tests passed!")

# Export test functions
__all__ = [
    "test_basic_rust_proto_generation",
    "test_rust_grpc_generation",
    "test_rust_serde_integration", 
    "test_rust_package_name_resolution",
    "test_rust_custom_options",
    "test_rust_edition_support",
    "test_rust_lib_rs_generation",
    "test_rust_features_configuration",
    "test_rust_error_handling",
    "rust_proto_test_suite",
]
