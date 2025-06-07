"""Implementation utilities for advanced gRPC service generation.

This module provides the core logic for generating gRPC services with advanced
features like gRPC-Gateway, OpenAPI documentation, validation, and mocking.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "GrpcServiceInfo", "PluginInfo")
load("//rules/private:bundle_impl.bzl", "SUPPORTED_LANGUAGES")
load("//rules:tools.bzl", "ensure_tools_available", "TOOL_ATTRS")

# Advanced plugin configurations
ADVANCED_PLUGINS = {
    "grpc-gateway": {
        "languages": ["go"],
        "tools": ["protoc-gen-grpc-gateway", "protoc-gen-openapiv2"],
        "outputs": ["*.pb.gw.go", "*.swagger.json"],
        "dependencies": ["github.com/grpc-ecosystem/grpc-gateway/v2"],
        "description": "HTTP/JSON to gRPC proxy generation",
    },
    "openapi": {
        "languages": ["all"],
        "tools": ["protoc-gen-openapiv2"],
        "outputs": ["*.swagger.json", "openapi.yaml"],
        "dependencies": [],
        "description": "OpenAPI/Swagger documentation generation",
    },
    "validate": {
        "languages": ["go", "python"],
        "tools": ["protoc-gen-validate"],
        "outputs": ["*.pb.validate.go", "*_pb2_validate.py"],
        "dependencies": ["github.com/envoyproxy/protoc-gen-validate"],
        "description": "Request/response validation generation",
    },
    "mock": {
        "languages": ["go", "python", "typescript"],
        "tools": ["protoc-gen-mock"],
        "outputs": ["*_mock.go", "*_mock.py", "*_mock.ts"],
        "dependencies": ["github.com/golang/mock"],
        "description": "Mock implementation generation",
    },
    "grpc-web": {
        "languages": ["typescript", "javascript"],
        "tools": ["protoc-gen-grpc-web"],
        "outputs": ["*_grpc_web_pb.js", "*_grpc_web_pb.d.ts"],
        "dependencies": ["grpc-web"],
        "description": "gRPC-Web browser client generation",
    },
}

def validate_grpc_service_config(languages, plugins, service_config):
    """
    Validates the gRPC service configuration.
    
    Args:
        languages: List of target languages
        plugins: Dictionary of plugin configurations
        service_config: Service-specific configuration
        
    Returns:
        Tuple of (validated_languages, validated_plugins, validated_config)
        
    Raises:
        fail() if configuration is invalid
    """
    # Validate languages
    validated_languages = []
    for lang in languages:
        if lang not in SUPPORTED_LANGUAGES:
            fail("Unsupported language '{}' for gRPC service. Supported: {}".format(
                lang, 
                ", ".join(SUPPORTED_LANGUAGES.keys())
            ))
        validated_languages.append(lang)
    
    # Validate plugins
    validated_plugins = {}
    for plugin_name, plugin_config in plugins.items():
        if plugin_name not in ADVANCED_PLUGINS:
            fail("Unsupported plugin '{}'. Supported plugins: {}".format(
                plugin_name,
                ", ".join(ADVANCED_PLUGINS.keys())
            ))
        
        plugin_info = ADVANCED_PLUGINS[plugin_name]
        
        # Check language compatibility
        supported_langs = plugin_info["languages"]
        if supported_langs != ["all"]:
            incompatible = [lang for lang in languages if lang not in supported_langs]
            if incompatible:
                fail("Plugin '{}' does not support languages: {}. Supported: {}".format(
                    plugin_name,
                    ", ".join(incompatible),
                    ", ".join(supported_langs)
                ))
        
        # Normalize plugin configuration
        normalized_plugin_config = {
            "enabled": plugin_config.get("enabled", True),
            "options": plugin_config.get("options", {}),
            "output_format": plugin_config.get("output_format", "default"),
        }
        
        # Add plugin-specific configuration
        if plugin_name == "grpc-gateway":
            normalized_plugin_config.update({
                "generate_unbound_methods": plugin_config.get("generate_unbound_methods", True),
                "register_func_suffix": plugin_config.get("register_func_suffix", "Handler"),
                "allow_patch_feature": plugin_config.get("allow_patch_feature", True),
            })
        elif plugin_name == "openapi":
            normalized_plugin_config.update({
                "output_format": plugin_config.get("output_format", "json"),
                "merge_file_name": plugin_config.get("merge_file_name", "api"),
                "include_package_in_tags": plugin_config.get("include_package_in_tags", True),
            })
        elif plugin_name == "validate":
            normalized_plugin_config.update({
                "lang": plugin_config.get("lang", "go"),
                "emit_imported_vars": plugin_config.get("emit_imported_vars", True),
            })
        elif plugin_name == "mock":
            normalized_plugin_config.update({
                "source": plugin_config.get("source", "auto"),
                "destination": plugin_config.get("destination", "auto"),
                "package": plugin_config.get("package", "mocks"),
            })
        
        validated_plugins[plugin_name] = normalized_plugin_config
    
    # Validate service configuration
    validated_config = {
        "timeout": service_config.get("timeout", "30s"),
        "retry_policy": service_config.get("retry_policy", {}),
        "load_balancing": service_config.get("load_balancing", "round_robin"),
        "health_check": service_config.get("health_check", True),
        "reflection": service_config.get("reflection", True),
    }
    
    return validated_languages, validated_plugins, validated_config

def generate_grpc_gateway_code(ctx, proto_info, plugin_config, output_dir):
    """
    Generates gRPC-Gateway HTTP/JSON proxy code for Go.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider
        plugin_config: gRPC-Gateway plugin configuration
        output_dir: Output directory for generated files
        
    Returns:
        List of generated file objects
    """
    if not plugin_config.get("enabled", True):
        return []
    
    tools = ensure_tools_available(ctx, "go")
    generated_files = []
    
    # Generate gRPC-Gateway files
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # Gateway implementation file
        gateway_file = ctx.actions.declare_output(output_dir, base_name + ".pb.gw.go")
        generated_files.append(gateway_file)
        
        # OpenAPI/Swagger documentation
        if plugin_config.get("generate_openapi", True):
            swagger_file = ctx.actions.declare_output(output_dir, base_name + ".swagger.json")
            generated_files.append(swagger_file)
    
    # Build protoc command for gRPC-Gateway
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure gRPC-Gateway plugin
    protoc_cmd.add("--plugin=protoc-gen-grpc-gateway={}".format(tools["protoc-gen-grpc-gateway"]))
    protoc_cmd.add("--grpc-gateway_out={}".format(output_dir))
    
    # Add gRPC-Gateway options
    gateway_options = []
    if plugin_config.get("generate_unbound_methods"):
        gateway_options.append("generate_unbound_methods=true")
    if plugin_config.get("register_func_suffix"):
        gateway_options.append("register_func_suffix={}".format(plugin_config["register_func_suffix"]))
    if plugin_config.get("allow_patch_feature"):
        gateway_options.append("allow_patch_feature=true")
    
    if gateway_options:
        protoc_cmd.add("--grpc-gateway_opt={}".format(",".join(gateway_options)))
    
    # Configure OpenAPI generation if enabled
    if plugin_config.get("generate_openapi", True):
        protoc_cmd.add("--plugin=protoc-gen-openapiv2={}".format(tools["protoc-gen-openapiv2"]))
        protoc_cmd.add("--openapiv2_out={}".format(output_dir))
        
        openapi_options = []
        if plugin_config.get("merge_file_name"):
            openapi_options.append("merge_file_name={}".format(plugin_config["merge_file_name"]))
        if plugin_config.get("include_package_in_tags"):
            openapi_options.append("include_package_in_tags=true")
        
        if openapi_options:
            protoc_cmd.add("--openapiv2_opt={}".format(",".join(openapi_options)))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect inputs
    inputs = [tools["protoc"], tools["protoc-gen-grpc-gateway"]] + proto_info.proto_files
    if "protoc-gen-openapiv2" in tools:
        inputs.append(tools["protoc-gen-openapiv2"])
    
    # Execute protoc
    ctx.actions.run(
        protoc_cmd,
        category = "grpc_gateway",
        identifier = "{}_grpc_gateway".format(ctx.label.name),
        inputs = inputs,
        outputs = generated_files,
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin"},
        local_only = False,
    )
    
    return generated_files

def generate_validation_code(ctx, proto_info, plugin_config, languages, output_dir):
    """
    Generates validation code using protoc-gen-validate.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider
        plugin_config: Validation plugin configuration
        languages: Target languages for validation
        output_dir: Output directory for generated files
        
    Returns:
        List of generated file objects
    """
    if not plugin_config.get("enabled", True):
        return []
    
    tools = ensure_tools_available(ctx, "validation")
    generated_files = []
    
    # Generate validation files for each language
    for lang in languages:
        if lang not in ["go", "python"]:
            continue  # Skip unsupported languages
        
        for proto_file in proto_info.proto_files:
            base_name = proto_file.basename
            if base_name.endswith(".proto"):
                base_name = base_name[:-6]
            
            if lang == "go":
                validate_file = ctx.actions.declare_output(output_dir, lang, base_name + ".pb.validate.go")
                generated_files.append(validate_file)
            elif lang == "python":
                validate_file = ctx.actions.declare_output(output_dir, lang, base_name + "_pb2_validate.py")
                generated_files.append(validate_file)
    
    # Build protoc command for validation
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure validation plugin for each language
    for lang in languages:
        if lang == "go":
            protoc_cmd.add("--plugin=protoc-gen-validate={}".format(tools["protoc-gen-validate"]))
            protoc_cmd.add("--validate_out=lang=go:{}".format(output_dir + "/go"))
        elif lang == "python":
            protoc_cmd.add("--plugin=protoc-gen-validate={}".format(tools["protoc-gen-validate"]))
            protoc_cmd.add("--validate_out=lang=python:{}".format(output_dir + "/python"))
    
    # Add validation options
    validate_options = []
    if plugin_config.get("emit_imported_vars"):
        validate_options.append("emit_imported_vars=true")
    
    if validate_options:
        protoc_cmd.add("--validate_opt={}".format(",".join(validate_options)))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect inputs
    inputs = [tools["protoc"], tools["protoc-gen-validate"]] + proto_info.proto_files
    
    # Execute protoc
    ctx.actions.run(
        protoc_cmd,
        category = "validation",
        identifier = "{}_validation".format(ctx.label.name),
        inputs = inputs,
        outputs = generated_files,
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin"},
        local_only = False,
    )
    
    return generated_files

def generate_mock_code(ctx, proto_info, plugin_config, languages, output_dir):
    """
    Generates mock implementation code for testing.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider
        plugin_config: Mock plugin configuration
        languages: Target languages for mocks
        output_dir: Output directory for generated files
        
    Returns:
        List of generated file objects
    """
    if not plugin_config.get("enabled", True):
        return []
    
    generated_files = []
    
    # Generate mock files for each supported language
    for lang in languages:
        if lang not in ["go", "python", "typescript"]:
            continue  # Skip unsupported languages
        
        for proto_file in proto_info.proto_files:
            base_name = proto_file.basename
            if base_name.endswith(".proto"):
                base_name = base_name[:-6]
            
            if lang == "go":
                mock_file = ctx.actions.declare_output(output_dir, lang, base_name + "_mock.go")
            elif lang == "python":
                mock_file = ctx.actions.declare_output(output_dir, lang, base_name + "_mock.py")
            elif lang == "typescript":
                mock_file = ctx.actions.declare_output(output_dir, lang, base_name + "_mock.ts")
            
            generated_files.append(mock_file)
            
            # Create mock implementation content
            mock_content = _generate_mock_content(lang, base_name, proto_info, plugin_config)
            
            ctx.actions.write(
                mock_file,
                mock_content,
            )
    
    return generated_files

def _generate_mock_content(language, base_name, proto_info, plugin_config):
    """
    Generates mock implementation content for a specific language.
    
    Args:
        language: Target language
        base_name: Base name of the proto file
        proto_info: ProtoInfo provider
        plugin_config: Mock plugin configuration
        
    Returns:
        String containing mock implementation code
    """
    if language == "go":
        return """// Code generated by protoc-gen-mock. DO NOT EDIT.
// source: {}.proto

package {}

import (
    "context"
    
    "github.com/golang/mock/gomock"
    "google.golang.org/grpc"
)

// Mock{} is a mock implementation of the {} service.
type Mock{} struct {{
    ctrl     *gomock.Controller
    recorder *Mock{}Recorder
}}

// Mock{}Recorder is the mock recorder for Mock{}.
type Mock{}Recorder struct {{
    mock *Mock{}
}}

// NewMock{} creates a new mock instance.
func NewMock{}(ctrl *gomock.Controller) *Mock{} {{
    mock := &Mock{{ctrl: ctrl}}
    mock.recorder = &Mock{}Recorder{{mock}}
    return mock
}}

// EXPECT returns an object that allows the caller to indicate expected use.
func (m *Mock{}) EXPECT() *Mock{}Recorder {{
    return m.recorder
}}

// Example mock method - replace with actual service methods
func (m *Mock{}) ExampleMethod(ctx context.Context, req *ExampleRequest, opts ...grpc.CallOption) (*ExampleResponse, error) {{
    m.ctrl.T.Helper()
    ret := m.ctrl.Call(m, "ExampleMethod", ctx, req, opts)
    ret0, _ := ret[0].(*ExampleResponse)
    ret1, _ := ret[1].(error)
    return ret0, ret1
}}

// ExampleMethod indicates an expected call of ExampleMethod.
func (mr *Mock{}Recorder) ExampleMethod(ctx, req interface{{}}, opts ...interface{{}}) *gomock.Call {{
    mr.mock.ctrl.T.Helper()
    varargs := append([]interface{{}}{{ctx, req}}, opts...)
    return mr.mock.ctrl.RecordCallWithMethodType(mr.mock, "ExampleMethod", reflect.TypeOf((*Mock{})(nil).ExampleMethod), varargs...)
}}
""".format(
            base_name, 
            plugin_config.get("package", "mocks"),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
        )
    elif language == "python":
        return """\"\"\"Generated mock implementation for {}.proto.

This file contains mock implementations for testing purposes.
DO NOT EDIT - generated by protoc-gen-mock.
\"\"\"

from unittest.mock import Mock, MagicMock
from typing import Any, Dict, Optional


class Mock{}Service:
    \"\"\"Mock implementation of the {} service.\"\"\"
    
    def __init__(self):
        self._mock = Mock()
        self._responses = {{}}
    
    def set_response(self, method_name: str, response: Any) -> None:
        \"\"\"Set a canned response for a method.\"\"\"
        self._responses[method_name] = response
    
    def get_call_count(self, method_name: str) -> int:
        \"\"\"Get the number of times a method was called.\"\"\"
        return getattr(self._mock, method_name).call_count
    
    def get_call_args(self, method_name: str) -> tuple:
        \"\"\"Get the arguments from the last call to a method.\"\"\"
        return getattr(self._mock, method_name).call_args
    
    # Example mock method - replace with actual service methods
    def example_method(self, request, context=None):
        \"\"\"Mock implementation of example_method.\"\"\"
        self._mock.example_method(request, context)
        return self._responses.get('example_method', {{}})


# Convenience function to create a mock service
def create_mock_{}_service() -> Mock{}Service:
    \"\"\"Creates a new mock {} service instance.\"\"\"
    return Mock{}Service()
""".format(
            base_name,
            base_name.title(),
            base_name,
            base_name,
            base_name.title(),
            base_name,
            base_name.title(),
        )
    elif language == "typescript":
        return """/**
 * Generated mock implementation for {}.proto
 * 
 * This file contains mock implementations for testing purposes.
 * DO NOT EDIT - generated by protoc-gen-mock.
 */

export interface Mock{}ServiceOptions {{
  responses?: Map<string, any>;
  throwErrors?: boolean;
}}

export class Mock{}Service {{
  private responses = new Map<string, any>();
  private callCounts = new Map<string, number>();
  private callArgs = new Map<string, any[]>();
  private throwErrors = false;
  
  constructor(options: Mock{}ServiceOptions = {{}}) {{
    if (options.responses) {{
      this.responses = options.responses;
    }}
    this.throwErrors = options.throwErrors || false;
  }}
  
  /**
   * Set a canned response for a method.
   */
  setResponse(methodName: string, response: any): void {{
    this.responses.set(methodName, response);
  }}
  
  /**
   * Get the number of times a method was called.
   */
  getCallCount(methodName: string): number {{
    return this.callCounts.get(methodName) || 0;
  }}
  
  /**
   * Get the arguments from the last call to a method.
   */
  getCallArgs(methodName: string): any[] {{
    return this.callArgs.get(methodName) || [];
  }}
  
  /**
   * Reset all call tracking.
   */
  reset(): void {{
    this.callCounts.clear();
    this.callArgs.clear();
  }}
  
  // Example mock method - replace with actual service methods
  exampleMethod(request: any): Promise<any> {{
    this._recordCall('exampleMethod', [request]);
    
    if (this.throwErrors) {{
      throw new Error('Mock error for exampleMethod');
    }}
    
    return Promise.resolve(this.responses.get('exampleMethod') || {{}});
  }}
  
  private _recordCall(methodName: string, args: any[]): void {{
    const count = this.callCounts.get(methodName) || 0;
    this.callCounts.set(methodName, count + 1);
    this.callArgs.set(methodName, args);
  }}
}}

/**
 * Convenience function to create a mock service.
 */
export function createMock{}Service(options?: Mock{}ServiceOptions): Mock{}Service {{
  return new Mock{}Service(options);
}}
""".format(
            base_name,
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
            base_name.title(),
        )
    
    return "// Mock implementation placeholder"

def create_grpc_service_info(ctx, service_name, proto_target, languages, plugins, gateway_files, openapi_files, validation_files, mock_files, service_config):
    """
    Creates a GrpcServiceInfo provider with complete service information.
    
    Args:
        ctx: Buck2 rule context
        service_name: Name of the gRPC service
        proto_target: Proto library containing service definitions
        languages: List of target languages
        plugins: Dictionary of enabled plugins and their configurations
        gateway_files: gRPC-Gateway generated files
        openapi_files: OpenAPI/Swagger files
        validation_files: Validation plugin files
        mock_files: Mock implementation files
        service_config: Service-specific configuration
        
    Returns:
        GrpcServiceInfo provider
    """
    return GrpcServiceInfo(
        service_name = service_name,
        proto_target = proto_target,
        languages = languages,
        plugins = plugins,
        gateway_files = gateway_files,
        openapi_files = openapi_files,
        validation_files = validation_files,
        mock_files = mock_files,
        service_config = service_config,
    )
