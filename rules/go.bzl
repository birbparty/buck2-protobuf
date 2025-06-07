"""Go protobuf generation rules for Buck2.

This module provides rules for generating Go code from protobuf definitions.
Supports both basic protobuf messages and gRPC service stubs with proper
Go module integration.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo", "PerformanceInfo", "PerformanceMetricsInfo")
load("//rules/private:utils.bzl", "get_proto_import_path")
load("//rules/private:performance_impl.bzl", "create_performance_optimized_action", "get_default_performance_config")
load("//rules/private:cache_impl.bzl", "get_default_cache_config")
load("//rules:tools.bzl", "ensure_tools_available", "TOOL_ATTRS", "get_protoc_command")

def go_proto_library(
    name: str,
    proto: str,
    go_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    plugins: list[str] = ["go", "go-grpc"],
    options: dict[str, str] = {},
    go_module: str = "",
    embed: list[str] = [],
    **kwargs
):
    """
    Generates Go code from a proto_library target.
    
    Args:
        name: Unique name for this Go protobuf library target
        proto: proto_library target to generate Go code from
        go_package: Go package path override (e.g., "github.com/org/pkg/v1")
        visibility: Buck2 visibility specification
        plugins: List of protoc plugins to use ["go", "go-grpc", "grpc-gateway", "validate"]
        options: Additional protoc options for Go generation
        go_module: Go module name for generated go.mod file
        embed: Additional files to include in the Go package
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        go_proto_library(
            name = "user_go_proto",
            proto = ":user_proto",
            go_package = "github.com/org/user/v1",
            plugins = ["go", "go-grpc"],
            visibility = ["PUBLIC"],
        )
        
    Generated Files:
        - *.pb.go: Basic protobuf message code (protoc-gen-go)
        - *_grpc.pb.go: gRPC service stubs (protoc-gen-go-grpc)
        - go.mod: Go module definition (if go_module specified)
    """
    go_proto_library_rule(
        name = name,
        proto = proto,
        go_package = go_package,
        visibility = visibility,
        plugins = plugins,
        options = options,
        go_module = go_module,
        embed = embed,
        **kwargs
    )

def _resolve_go_package(ctx, proto_info):
    """
    Resolves the Go package path for generated code.
    
    Priority order:
    1. Explicit go_package parameter
    2. go_package option from proto file
    3. Generated package based on proto file path
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        String containing the resolved Go package path
    """
    # 1. Check explicit parameter
    if ctx.attrs.go_package:
        return ctx.attrs.go_package
    
    # 2. Check proto file option
    if proto_info.go_package:
        return proto_info.go_package
    
    # 3. Generate from proto file path
    if proto_info.proto_files:
        proto_file = proto_info.proto_files[0]
        return _generate_go_package_from_path(proto_file.short_path)
    
    fail("Could not resolve Go package path for proto target")

def _generate_go_package_from_path(proto_path: str) -> str:
    """
    Generates a Go package path from a proto file path.
    
    Args:
        proto_path: Path to the proto file (e.g., "pkg/user/user.proto")
        
    Returns:
        Generated Go package path (e.g., "pkg/user")
    """
    # Remove .proto extension and get directory
    if proto_path.endswith(".proto"):
        proto_path = proto_path[:-6]
    
    # Get directory path
    parts = proto_path.split("/")
    if len(parts) > 1:
        return "/".join(parts[:-1])
    else:
        return "."

def _get_go_output_files(ctx, proto_info, go_package: str):
    """
    Determines the expected Go output files based on proto content and plugins.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        go_package: Resolved Go package path
        
    Returns:
        List of expected output file objects
    """
    output_files = []
    
    # Base name from proto files
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # Basic protobuf messages (always generated if "go" plugin enabled)
        if "go" in ctx.attrs.plugins:
            pb_go_file = ctx.actions.declare_output("go", base_name + ".pb.go")
            output_files.append(pb_go_file)
        
        # gRPC service stubs (if "go-grpc" plugin enabled and proto has services)
        if "go-grpc" in ctx.attrs.plugins:
            grpc_pb_go_file = ctx.actions.declare_output("go", base_name + "_grpc.pb.go")
            output_files.append(grpc_pb_go_file)
    
    # go.mod file (if go_module specified)
    if ctx.attrs.go_module:
        go_mod_file = ctx.actions.declare_output("go", "go.mod")
        output_files.append(go_mod_file)
    
    return output_files

def _create_go_mod_content(go_module: str) -> str:
    """
    Creates go.mod file content for generated Go code.
    
    Args:
        go_module: Go module name
        
    Returns:
        String content for go.mod file
    """
    return """module {module}

go 1.21

require (
    google.golang.org/protobuf v1.31.0
    google.golang.org/grpc v1.59.0
)
""".format(module = go_module)

def _generate_go_code(ctx, proto_info, tools, output_files, go_package: str):
    """
    Executes protoc with Go plugins to generate Go code.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        tools: Dictionary of tool file objects
        output_files: List of expected output files
        go_package: Resolved Go package path
    """
    # Create output directory
    output_dir = ctx.actions.declare_output("go")
    
    # Build protoc command arguments
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths (current + transitive)
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure Go code generation
    if "go" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-go={}".format(tools["protoc-gen-go"]))
        protoc_cmd.add("--go_out={}".format(output_dir.as_output()))
        protoc_cmd.add("--go_opt=paths=source_relative")
        
        # Add custom Go package mapping if specified
        if go_package:
            for proto_file in proto_info.proto_files:
                protoc_cmd.add("--go_opt=M{}={}".format(
                    proto_file.short_path, 
                    go_package
                ))
    
    # Configure gRPC service generation
    if "go-grpc" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-go-grpc={}".format(tools["protoc-gen-go-grpc"]))
        protoc_cmd.add("--go-grpc_out={}".format(output_dir.as_output()))
        protoc_cmd.add("--go-grpc_opt=paths=source_relative")
        
        # Add custom gRPC package mapping if specified
        if go_package:
            for proto_file in proto_info.proto_files:
                protoc_cmd.add("--go-grpc_opt=M{}={}".format(
                    proto_file.short_path, 
                    go_package
                ))
    
    # Add any additional options
    for opt_key, opt_value in ctx.attrs.options.items():
        if opt_key.startswith("go_"):
            protoc_cmd.add("--go_opt={}={}".format(opt_key[3:], opt_value))
        elif opt_key.startswith("go_grpc_"):
            protoc_cmd.add("--go-grpc_opt={}={}".format(opt_key[8:], opt_value))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect all inputs
    inputs = [tools["protoc"]] + proto_info.proto_files + proto_info.transitive_descriptor_sets
    if "protoc-gen-go" in tools:
        inputs.append(tools["protoc-gen-go"])
    if "protoc-gen-go-grpc" in tools:
        inputs.append(tools["protoc-gen-go-grpc"])
    
    # Run protoc to generate Go code
    ctx.actions.run(
        protoc_cmd,
        category = "go_protoc",
        identifier = "{}_go_generation".format(ctx.label.name),
        inputs = inputs,
        outputs = [output_dir] + output_files,
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
        local_only = False,
    )

def _create_go_mod_file(ctx, go_module: str):
    """
    Creates a go.mod file for the generated Go code.
    
    Args:
        ctx: Buck2 rule context
        go_module: Go module name
        
    Returns:
        File object for the generated go.mod file
    """
    go_mod_file = ctx.actions.declare_output("go", "go.mod")
    go_mod_content = _create_go_mod_content(go_module)
    
    ctx.actions.write(
        go_mod_file,
        go_mod_content,
    )
    
    return go_mod_file

def _go_proto_library_impl(ctx):
    """
    Implementation function for go_proto_library rule.
    
    Handles:
    - Go package path resolution
    - Tool downloading and caching
    - protoc execution with Go plugins
    - go.mod file generation
    - Output file management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Resolve Go package path
    go_package = _resolve_go_package(ctx, proto_info)
    
    # Ensure required tools are available
    tools = ensure_tools_available(ctx, "go")
    
    # Get expected output files
    output_files = _get_go_output_files(ctx, proto_info, go_package)
    
    # Generate Go code using protoc
    _generate_go_code(ctx, proto_info, tools, output_files, go_package)
    
    # Create go.mod file if requested
    go_mod_file = None
    if ctx.attrs.go_module:
        go_mod_file = _create_go_mod_file(ctx, ctx.attrs.go_module)
        output_files.append(go_mod_file)
    
    # Create LanguageProtoInfo provider
    language_proto_info = LanguageProtoInfo(
        language = "go",
        generated_files = output_files,
        package_name = go_package,
        dependencies = [
            "google.golang.org/protobuf",
            "google.golang.org/grpc",
        ] if "go-grpc" in ctx.attrs.plugins else ["google.golang.org/protobuf"],
        compiler_flags = [],
    )
    
    # Return providers
    return [
        DefaultInfo(default_outputs = output_files),
        language_proto_info,
    ]

# Go protobuf library rule definition
go_proto_library_rule = rule(
    impl = _go_proto_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "go_package": attrs.string(default = "", doc = "Go package path override"),
        "plugins": attrs.list(attrs.string(), default = ["go", "go-grpc"], doc = "Protoc plugins to use"),
        "options": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Additional protoc options"),
        "go_module": attrs.string(default = "", doc = "Go module name for go.mod file"),
        "embed": attrs.list(attrs.source(), default = [], doc = "Additional files to embed"),
        "_protoc": attrs.exec_dep(default = "//tools:protoc"),
        "_protoc_gen_go": attrs.exec_dep(default = "//tools:protoc-gen-go", doc = "Go protoc plugin"),
        "_protoc_gen_go_grpc": attrs.exec_dep(default = "//tools:protoc-gen-go-grpc", doc = "Go gRPC protoc plugin"),
    },
)

# Convenience function for basic Go protobuf generation (messages only)
def go_proto_messages(
    name: str,
    proto: str,
    go_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates only Go protobuf message code (no gRPC services).
    
    This is a convenience wrapper around go_proto_library that only
    generates basic protobuf message types, excluding gRPC service stubs.
    
    Args:
        name: Target name
        proto: proto_library target
        go_package: Go package path override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    go_proto_library(
        name = name,
        proto = proto,
        go_package = go_package,
        visibility = visibility,
        plugins = ["go"],  # Only basic protobuf, no gRPC
        **kwargs
    )

# Convenience function for gRPC service generation
def go_grpc_library(
    name: str,
    proto: str,
    go_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates Go gRPC service stubs with both messages and service definitions.
    
    This is a convenience wrapper around go_proto_library that ensures
    both protobuf messages and gRPC service stubs are generated.
    
    Args:
        name: Target name
        proto: proto_library target (must contain service definitions)
        go_package: Go package path override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    go_proto_library(
        name = name,
        proto = proto,
        go_package = go_package,
        visibility = visibility,
        plugins = ["go", "go-grpc"],  # Both messages and gRPC services
        **kwargs
    )
