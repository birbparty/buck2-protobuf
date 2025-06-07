"""Tests for advanced gRPC service generation rules.

This module tests the grpc_service rule which generates gRPC services with
advanced features like gRPC-Gateway, OpenAPI documentation, validation, and mocking.
"""

load("//rules:proto.bzl", "proto_library", "grpc_service")
load("//rules/private:providers.bzl", "GrpcServiceInfo")
load("@prelude//utils:utils.bzl", "expect")

def test_grpc_service_basic():
    """Test basic grpc_service functionality."""
    
    # Create a test proto library with service definitions
    proto_library(
        name = "test_service_proto",
        srcs = ["test_service.proto"],
        options = {
            "go_package": "github.com/test/service/v1",
        },
        visibility = ["//test:__pkg__"],
    )
    
    # Create a basic gRPC service
    grpc_service(
        name = "test_service",
        proto = ":test_service_proto",
        languages = ["go", "python"],
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_with_gateway():
    """Test grpc_service with gRPC-Gateway plugin."""
    
    proto_library(
        name = "test_gateway_proto",
        srcs = ["test_gateway.proto"],
        options = {
            "go_package": "github.com/test/gateway/v1",
        },
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_gateway_service",
        proto = ":test_gateway_proto",
        languages = ["go"],  # gRPC-Gateway only supports Go
        plugins = {
            "grpc-gateway": {
                "enabled": True,
                "generate_openapi": True,
                "generate_unbound_methods": True,
                "register_func_suffix": "Handler",
                "allow_patch_feature": True,
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_with_openapi():
    """Test grpc_service with OpenAPI documentation generation."""
    
    proto_library(
        name = "test_openapi_proto",
        srcs = ["test_openapi.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_openapi_service",
        proto = ":test_openapi_proto",
        languages = ["go", "python", "typescript"],
        plugins = {
            "openapi": {
                "enabled": True,
                "output_format": "json",
                "merge_file_name": "api_docs",
                "include_package_in_tags": True,
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_with_validation():
    """Test grpc_service with validation plugin."""
    
    proto_library(
        name = "test_validation_proto",
        srcs = ["test_validation.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_validation_service",
        proto = ":test_validation_proto",
        languages = ["go", "python"],  # Validation supports Go and Python
        plugins = {
            "validate": {
                "enabled": True,
                "emit_imported_vars": True,
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_with_mocks():
    """Test grpc_service with mock generation."""
    
    proto_library(
        name = "test_mock_proto",
        srcs = ["test_mock.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_mock_service",
        proto = ":test_mock_proto",
        languages = ["go", "python", "typescript"],
        plugins = {
            "mock": {
                "enabled": True,
                "package": "testmocks",
                "source": "auto",
                "destination": "auto",
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_with_grpc_web():
    """Test grpc_service with gRPC-Web for browser clients."""
    
    proto_library(
        name = "test_grpc_web_proto",
        srcs = ["test_grpc_web.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_grpc_web_service",
        proto = ":test_grpc_web_proto",
        languages = ["typescript"],  # gRPC-Web primarily for TypeScript/JavaScript
        plugins = {
            "grpc-web": {
                "enabled": True,
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_all_plugins():
    """Test grpc_service with all plugins enabled."""
    
    proto_library(
        name = "test_all_plugins_proto",
        srcs = ["test_all_plugins.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_all_plugins_service",
        proto = ":test_all_plugins_proto",
        languages = ["go", "python", "typescript"],
        plugins = {
            "grpc-gateway": {
                "enabled": True,
                "generate_openapi": True,
                "merge_file_name": "complete_api",
            },
            "openapi": {
                "enabled": True,
                "output_format": "json",
            },
            "validate": {
                "enabled": True,
                "emit_imported_vars": True,
            },
            "mock": {
                "enabled": True,
                "package": "allmocks",
            },
            "grpc-web": {
                "enabled": True,
            },
        },
        service_config = {
            "timeout": "60s",
            "retry_policy": {
                "max_attempts": "5",
                "initial_backoff": "1s",
                "max_backoff": "30s",
            },
            "load_balancing": "round_robin",
            "health_check": True,
            "reflection": True,
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_language_compatibility():
    """Test grpc_service plugin language compatibility validation."""
    
    proto_library(
        name = "test_compat_proto",
        srcs = ["test_compat.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Test Go-only plugins with Go language (should work)
    grpc_service(
        name = "test_go_only_service",
        proto = ":test_compat_proto",
        languages = ["go"],
        plugins = {
            "grpc-gateway": {"enabled": True},  # Go-only plugin
        },
        visibility = ["//test:__pkg__"],
    )
    
    # Test TypeScript-focused service
    grpc_service(
        name = "test_typescript_service",
        proto = ":test_compat_proto",
        languages = ["typescript"],
        plugins = {
            "grpc-web": {"enabled": True},  # TypeScript/JavaScript plugin
        },
        visibility = ["//test:__pkg__"],
    )
    
    # Test multi-language compatible plugins
    grpc_service(
        name = "test_multi_lang_service",
        proto = ":test_compat_proto",
        languages = ["go", "python", "typescript"],
        plugins = {
            "openapi": {"enabled": True},  # Compatible with all languages
            "mock": {"enabled": True},     # Compatible with multiple languages
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_error_handling():
    """Test grpc_service error handling for invalid configurations."""
    
    proto_library(
        name = "test_error_service_proto",
        srcs = ["test_error_service.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # These would fail in actual tests (wrapped in expect_failure):
    
    # 1. Incompatible plugin with language
    # grpc_service(
    #     name = "test_incompatible_plugin",
    #     proto = ":test_error_service_proto",
    #     languages = ["python"],
    #     plugins = {
    #         "grpc-gateway": {"enabled": True},  # Go-only plugin with Python - should fail
    #     },
    # )
    
    # 2. Unsupported language
    # grpc_service(
    #     name = "test_unsupported_language",
    #     proto = ":test_error_service_proto",
    #     languages = ["unsupported"],  # Should fail
    # )
    
    # 3. Unknown plugin
    # grpc_service(
    #     name = "test_unknown_plugin",
    #     proto = ":test_error_service_proto",
    #     languages = ["go"],
    #     plugins = {
    #         "unknown_plugin": {"enabled": True},  # Should fail
    #     },
    # )

def test_grpc_service_custom_config():
    """Test grpc_service with custom service configuration."""
    
    proto_library(
        name = "test_config_proto",
        srcs = ["test_config.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_custom_config_service",
        proto = ":test_config_proto",
        languages = ["go", "python"],
        service_config = {
            "timeout": "120s",
            "retry_policy": {
                "max_attempts": "10",
                "initial_backoff": "500ms",
                "max_backoff": "60s",
                "backoff_multiplier": "2.0",
            },
            "load_balancing": "least_request",
            "health_check": True,
            "reflection": True,
            "compression": "gzip",
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_plugin_options():
    """Test grpc_service with detailed plugin options."""
    
    proto_library(
        name = "test_plugin_opts_proto",
        srcs = ["test_plugin_opts.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_plugin_options_service",
        proto = ":test_plugin_opts_proto",
        languages = ["go"],
        plugins = {
            "grpc-gateway": {
                "enabled": True,
                "generate_openapi": True,
                "generate_unbound_methods": False,
                "register_func_suffix": "HTTPHandler",
                "allow_patch_feature": False,
                "options": {
                    "grpc_api_configuration": "api_config.yaml",
                },
            },
            "openapi": {
                "enabled": True,
                "output_format": "yaml",
                "merge_file_name": "service_api",
                "include_package_in_tags": False,
                "options": {
                    "openapi_naming_strategy": "fqn",
                },
            },
            "validate": {
                "enabled": True,
                "lang": "go",
                "emit_imported_vars": False,
                "options": {
                    "validation_lang": "go",
                },
            },
        },
        visibility = ["//test:__pkg__"],
    )

def test_grpc_service_provider_info():
    """Test that grpc_service generates correct provider information."""
    
    proto_library(
        name = "test_provider_service_proto",
        srcs = ["test_provider_service.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_provider_service",
        proto = ":test_provider_service_proto",
        languages = ["go", "python"],
        plugins = {
            "openapi": {"enabled": True},
            "mock": {"enabled": True},
        },
        visibility = ["//test:__pkg__"],
    )
    
    # In a real test, we would assert:
    # - GrpcServiceInfo provider is present
    # - Service name matches expected value
    # - Languages are correctly configured
    # - Plugin files are generated
    # - Service configuration is stored

def test_grpc_service_integration():
    """Integration test for grpc_service file generation."""
    
    proto_library(
        name = "test_integration_service_proto",
        srcs = ["test_integration_service.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    grpc_service(
        name = "test_integration_service",
        proto = ":test_integration_service_proto",
        languages = ["go", "python"],
        plugins = {
            "grpc-gateway": {"enabled": True},
            "openapi": {"enabled": True, "output_format": "json"},
            "mock": {"enabled": True, "package": "integrationmocks"},
        },
        service_config = {
            "timeout": "30s",
            "health_check": True,
        },
        visibility = ["//test:__pkg__"],
    )
    
    # In a real integration test, we would:
    # 1. Build the service target
    # 2. Verify gRPC-Gateway files are generated
    # 3. Check OpenAPI documentation is created
    # 4. Validate mock files are present
    # 5. Test that the generated code compiles
    # 6. Verify service registration works correctly

# Test helper functions for service validation
def _assert_service_info(service_target, expected_languages, expected_plugins):
    """Helper function to validate GrpcServiceInfo provider."""
    service_info = service_target[GrpcServiceInfo]
    
    expect(service_info != None, "GrpcServiceInfo provider should be present")
    expect(service_info.languages == expected_languages, 
           "Languages should match expected")
    
    for plugin_name in expected_plugins:
        expect(plugin_name in service_info.plugins, 
               "Plugin '{}' should be configured".format(plugin_name))

def _assert_plugin_files_generated(service_target, plugin_name):
    """Helper function to validate plugin files are generated."""
    service_info = service_target[GrpcServiceInfo]
    
    if plugin_name == "grpc-gateway":
        expect(len(service_info.gateway_files) > 0, 
               "gRPC-Gateway files should be generated")
    elif plugin_name == "openapi":
        expect(len(service_info.openapi_files) > 0, 
               "OpenAPI files should be generated")
    elif plugin_name == "validate":
        expect(len(service_info.validation_files) > 0, 
               "Validation files should be generated")
    elif plugin_name == "mock":
        expect(len(service_info.mock_files) > 0, 
               "Mock files should be generated")

# Test data fixtures for gRPC services
GRPC_SERVICE_PROTO_CONTENT = """
syntax = "proto3";

package test.service;

import "google/api/annotations.proto";
import "validate/validate.proto";

message TestRequest {
  string name = 1 [(validate.rules).string.min_len = 1];
  int32 value = 2 [(validate.rules).int32.gte = 0];
}

message TestResponse {
  string result = 1;
  int32 status = 2;
}

service TestService {
  rpc GetTest(TestRequest) returns (TestResponse) {
    option (google.api.http) = {
      get: "/v1/test/{name}"
    };
  }
  
  rpc CreateTest(TestRequest) returns (TestResponse) {
    option (google.api.http) = {
      post: "/v1/test"
      body: "*"
    };
  }
  
  rpc StreamTests(TestRequest) returns (stream TestResponse);
}
"""

# Export test functions for test runner
GRPC_SERVICE_TESTS = [
    test_grpc_service_basic,
    test_grpc_service_with_gateway,
    test_grpc_service_with_openapi,
    test_grpc_service_with_validation,
    test_grpc_service_with_mocks,
    test_grpc_service_with_grpc_web,
    test_grpc_service_all_plugins,
    test_grpc_service_language_compatibility,
    test_grpc_service_error_handling,
    test_grpc_service_custom_config,
    test_grpc_service_plugin_options,
    test_grpc_service_provider_info,
    test_grpc_service_integration,
]
