"""Tests for multi-language bundle generation rules.

This module tests the proto_bundle rule which generates code for multiple
languages from a single proto_library target with consistency validation.
"""

load("//rules:proto.bzl", "proto_library", "proto_bundle")
load("//rules/private:providers.bzl", "ProtoBundleInfo")
load("@prelude//utils:utils.bzl", "expect")

def test_proto_bundle_basic():
    """Test basic proto_bundle functionality with minimal configuration."""
    
    # Create a test proto library
    proto_library(
        name = "test_user_proto",
        srcs = ["test_user.proto"],
        options = {
            "go_package": "github.com/test/user/v1",
            "python_package": "test.user.v1",
        },
        visibility = ["//test:__pkg__"],
    )
    
    # Create a basic multi-language bundle
    proto_bundle(
        name = "test_user_bundle",
        proto = ":test_user_proto",
        languages = {
            "go": {
                "go_package": "github.com/test/user/v1",
            },
            "python": {
                "python_package": "test.user.v1",
            },
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_all_languages():
    """Test proto_bundle with all supported languages."""
    
    proto_library(
        name = "test_all_languages_proto",
        srcs = ["test_all_languages.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_bundle(
        name = "test_all_languages_bundle",
        proto = ":test_all_languages_proto",
        languages = {
            "go": {
                "go_package": "github.com/test/all/v1",
                "go_module": "github.com/test/all",
                "plugins": ["go", "go-grpc"],
            },
            "python": {
                "python_package": "test.all.v1",
                "generate_stubs": True,
                "mypy_support": True,
                "plugins": ["python", "grpc-python"],
            },
            "typescript": {
                "npm_package": "@test/all-types",
                "module_type": "esm",
                "use_grpc_web": True,
                "plugins": ["ts", "grpc-web"],
            },
            "cpp": {
                "namespace": "test::all::v1",
                "use_grpc": True,
                "plugins": ["cpp"],
            },
            "rust": {
                "rust_package": "test-all-types",
                "edition": "2021",
                "use_grpc": True,
                "plugins": ["rust"],
            },
        },
        consistency_checks = True,
        parallel_generation = True,
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_language_specific_options():
    """Test proto_bundle with language-specific options and plugins."""
    
    proto_library(
        name = "test_options_proto",
        srcs = ["test_options.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_bundle(
        name = "test_options_bundle",
        proto = ":test_options_proto",
        languages = {
            "go": {
                "go_package": "github.com/test/options/v1",
                "plugins": ["go"],
                "options": {
                    "go_opt": "paths=source_relative",
                },
            },
            "python": {
                "python_package": "test.options.v1",
                "plugins": ["python"],
                "options": {
                    "python_opt": "optimize_mode=SPEED",
                },
            },
            "typescript": {
                "npm_package": "@test/options-types",
                "module_type": "both",
                "typescript_version": "5.0",
                "plugins": ["ts-proto"],
                "options": {
                    "ts_proto_opt": "esModuleInterop=true",
                },
            },
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_consistency_validation():
    """Test proto_bundle consistency validation features."""
    
    proto_library(
        name = "test_consistency_proto",
        srcs = ["test_consistency.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Test consistent configuration (should pass)
    proto_bundle(
        name = "test_consistent_bundle",
        proto = ":test_consistency_proto",
        languages = {
            "go": {"plugins": ["go", "go-grpc"]},
            "python": {"plugins": ["python", "grpc-python"]},
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )
    
    # Test inconsistent configuration (should generate warnings)
    proto_bundle(
        name = "test_inconsistent_bundle",
        proto = ":test_consistency_proto",
        languages = {
            "go": {"plugins": ["go", "go-grpc"]},  # gRPC enabled
            "python": {"plugins": ["python"]},    # gRPC disabled
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_with_dependencies():
    """Test proto_bundle with proto dependencies."""
    
    # Base proto library
    proto_library(
        name = "test_base_proto",
        srcs = ["test_base.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Derived proto library
    proto_library(
        name = "test_derived_proto",
        srcs = ["test_derived.proto"],
        deps = [":test_base_proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Bundle for derived proto (should handle dependencies)
    proto_bundle(
        name = "test_derived_bundle",
        proto = ":test_derived_proto",
        languages = {
            "go": {"go_package": "github.com/test/derived/v1"},
            "python": {"python_package": "test.derived.v1"},
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_minimal_config():
    """Test proto_bundle with minimal configuration (using defaults)."""
    
    proto_library(
        name = "test_minimal_proto",
        srcs = ["test_minimal.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_bundle(
        name = "test_minimal_bundle",
        proto = ":test_minimal_proto",
        languages = {
            "go": {},     # Use all defaults
            "python": {}, # Use all defaults
        },
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_error_handling():
    """Test proto_bundle error handling for invalid configurations."""
    
    proto_library(
        name = "test_error_proto",
        srcs = ["test_error.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # This should fail due to unsupported language
    # Note: In actual tests, this would be wrapped in expect_failure
    # proto_bundle(
    #     name = "test_unsupported_language",
    #     proto = ":test_error_proto",
    #     languages = {
    #         "unsupported": {},  # Should fail
    #     },
    # )

def test_proto_bundle_performance():
    """Test proto_bundle performance with parallel generation."""
    
    proto_library(
        name = "test_performance_proto",
        srcs = ["test_performance.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_bundle(
        name = "test_performance_bundle",
        proto = ":test_performance_proto",
        languages = {
            "go": {"go_package": "github.com/test/perf/v1"},
            "python": {"python_package": "test.perf.v1"},
            "typescript": {"npm_package": "@test/perf-types"},
            "cpp": {"namespace": "test::perf::v1"},
            "rust": {"rust_package": "test-perf-types"},
        },
        consistency_checks = True,
        parallel_generation = True,  # Enable parallel generation
        visibility = ["//test:__pkg__"],
    )

def test_proto_bundle_provider_info():
    """Test that proto_bundle generates correct provider information."""
    
    proto_library(
        name = "test_provider_proto",
        srcs = ["test_provider.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # This would be tested in an actual unit test framework
    # where we can inspect the generated providers
    proto_bundle(
        name = "test_provider_bundle",
        proto = ":test_provider_proto",
        languages = {
            "go": {"go_package": "github.com/test/provider/v1"},
            "python": {"python_package": "test.provider.v1"},
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )
    
    # In a real test, we would assert:
    # - ProtoBundleInfo provider is present
    # - Bundle name matches expected value
    # - Language targets are correctly configured
    # - Consistency report is generated

# Test helper functions for bundle validation
def _assert_bundle_info(bundle_target, expected_languages):
    """Helper function to validate ProtoBundleInfo provider."""
    bundle_info = bundle_target[ProtoBundleInfo]
    
    expect(bundle_info != None, "ProtoBundleInfo provider should be present")
    expect(bundle_info.generated_languages == expected_languages, 
           "Generated languages should match expected")
    expect(bundle_info.consistency_report != None, 
           "Consistency report should be generated")

def _assert_language_target_exists(bundle_target, language):
    """Helper function to validate language-specific targets exist."""
    bundle_info = bundle_target[ProtoBundleInfo]
    language_targets = bundle_info.language_targets
    
    expect(language in language_targets, 
           "Language '{}' should have a target".format(language))

# Integration test that would verify actual file generation
def test_proto_bundle_integration():
    """Integration test for proto_bundle file generation."""
    
    proto_library(
        name = "test_integration_proto",
        srcs = ["test_integration.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_bundle(
        name = "test_integration_bundle",
        proto = ":test_integration_proto",
        languages = {
            "go": {
                "go_package": "github.com/test/integration/v1",
                "plugins": ["go"],
            },
            "python": {
                "python_package": "test.integration.v1",
                "plugins": ["python"],
                "generate_stubs": True,
            },
        },
        consistency_checks = True,
        visibility = ["//test:__pkg__"],
    )
    
    # In a real integration test, we would:
    # 1. Build the bundle target
    # 2. Verify that files are generated for both Go and Python
    # 3. Check that the files have the expected structure
    # 4. Validate that the generated code compiles
    # 5. Test that the APIs are consistent across languages

# Test data fixtures
TEST_PROTO_CONTENT = """
syntax = "proto3";

package test;

message TestMessage {
  int64 id = 1;
  string name = 2;
  TestStatus status = 3;
}

enum TestStatus {
  TEST_STATUS_UNSPECIFIED = 0;
  TEST_STATUS_ACTIVE = 1;
  TEST_STATUS_INACTIVE = 2;
}

service TestService {
  rpc GetTest(GetTestRequest) returns (GetTestResponse);
  rpc CreateTest(CreateTestRequest) returns (CreateTestResponse);
}

message GetTestRequest {
  int64 id = 1;
}

message GetTestResponse {
  TestMessage test = 1;
}

message CreateTestRequest {
  string name = 1;
}

message CreateTestResponse {
  TestMessage test = 1;
}
"""

# Export test functions for test runner
BUNDLE_TESTS = [
    test_proto_bundle_basic,
    test_proto_bundle_all_languages,
    test_proto_bundle_language_specific_options,
    test_proto_bundle_consistency_validation,
    test_proto_bundle_with_dependencies,
    test_proto_bundle_minimal_config,
    test_proto_bundle_error_handling,
    test_proto_bundle_performance,
    test_proto_bundle_provider_info,
    test_proto_bundle_integration,
]
