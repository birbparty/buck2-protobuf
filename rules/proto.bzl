"""Core protobuf rules for Buck2.

This module provides the fundamental protobuf rules that serve as the foundation
for all language-specific code generation. These rules handle proto compilation,
dependency resolution, and provide the base infrastructure for the protobuf-buck2
integration.

The rules defined here follow the API specification and are implemented in Task 002.
"""

load("//rules/private:utils.bzl", "merge_proto_infos", "get_proto_import_path", "validate_proto_library_inputs", "create_descriptor_set_action", "get_proto_package_option")
load("//rules/private:providers.bzl", "ProtoInfo")

# Re-export ProtoInfo for external use
ProtoInfo = ProtoInfo

def proto_library(
    name,
    srcs,
    deps = [],
    visibility = ["//visibility:private"],
    import_prefix = "",
    strip_import_prefix = "",
    options = {},
    validation = {},
    well_known_types = True,
    protoc_version = "",
    **kwargs
):
    """
    Defines a protobuf library from .proto source files.
    
    This rule creates a protobuf library that can be consumed by language-specific
    generation rules. It handles proto file validation, dependency resolution,
    and creates the necessary artifacts for downstream code generation.
    
    Args:
        name: Unique name for this protobuf library target
        srcs: List of .proto files to include in this library
        deps: List of proto_library targets that this library depends on
        visibility: Buck2 visibility specification controlling who can depend on this
        import_prefix: Prefix to add to all import paths for this library
        strip_import_prefix: Prefix to strip from import paths when resolving
        options: Protobuf options to apply (go_package, java_package, etc.)
        validation: Validation configuration (see ValidationConfig below)
        well_known_types: Whether to include Google's well-known types
        protoc_version: Specific protoc version to use (defaults to global config)
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        proto_library(
            name = "user_proto",
            srcs = ["user.proto", "user_types.proto"],
            deps = ["//common:common_proto"],
            options = {
                "go_package": "github.com/org/user/v1",
                "java_package": "com.org.user.v1",
            },
            visibility = ["PUBLIC"],
        )
    """
    # Call the actual Buck2 rule
    proto_library_rule(
        name = name,
        srcs = srcs,
        deps = deps,
        visibility = visibility,
        import_prefix = import_prefix,
        strip_import_prefix = strip_import_prefix,
        options = options,
        validation = validation,
        well_known_types = well_known_types,
        protoc_version = protoc_version,
        **kwargs
    )

def _proto_library_impl(ctx):
    """Implementation function for proto_library rule.
    
    Handles:
    - Proto compilation with protoc
    - Dependency resolution and transitive deps
    - Descriptor set generation
    - Validation integration
    - Caching optimization
    """
    # Validate inputs
    validate_proto_library_inputs(ctx)
    
    # Get proto source files
    proto_files = ctx.attrs.srcs
    
    # Collect dependency ProtoInfo providers
    dep_proto_infos = []
    for dep in ctx.attrs.deps:
        if ProtoInfo in dep:
            dep_proto_infos.append(dep[ProtoInfo])
    
    # Merge transitive dependency information
    transitive_info = merge_proto_infos(dep_proto_infos)
    
    # Compute import paths for this library
    import_paths = []
    for src in proto_files:
        import_path = get_proto_import_path(
            src,
            ctx.attrs.import_prefix,
            ctx.attrs.strip_import_prefix
        )
        # Get the directory of the import path
        import_dir = "/".join(import_path.split("/")[:-1]) if "/" in import_path else "."
        if import_dir not in import_paths:
            import_paths.append(import_dir)
    
    # Add current directory as import path if not already present
    if "." not in import_paths:
        import_paths.append(".")
    
    # Create descriptor set via protoc compilation
    descriptor_set = create_descriptor_set_action(
        ctx,
        proto_files,
        transitive_info["transitive_descriptor_sets"],
        import_paths + transitive_info["transitive_import_paths"]
    )
    
    # Extract package options from proto files (for language-specific generation)
    go_package = ctx.attrs.options.get("go_package", "")
    python_package = ctx.attrs.options.get("python_package", "")
    java_package = ctx.attrs.options.get("java_package", "")
    
    # Note: In a production implementation, we would extract package options from proto files
    # For now, we rely on explicit options parameter since reading files at analysis time
    # has limitations in Buck2. This will be enhanced in later tasks.
    
    # Create ProtoInfo provider
    proto_info = ProtoInfo(
        descriptor_set = descriptor_set,
        proto_files = proto_files,
        import_paths = import_paths,
        transitive_descriptor_sets = transitive_info["transitive_descriptor_sets"] + [descriptor_set],
        transitive_proto_files = transitive_info["transitive_proto_files"] + proto_files,
        transitive_import_paths = transitive_info["transitive_import_paths"] + import_paths,
        go_package = go_package,
        python_package = python_package,
        java_package = java_package,
        lint_report = None,  # Will be implemented in validation tasks
        breaking_report = None,  # Will be implemented in validation tasks
    )
    
    # Return providers
    return [
        DefaultInfo(default_outputs = [descriptor_set]),
        proto_info,
    ]

# Proto library rule definition
proto_library_rule = rule(
    impl = _proto_library_impl,
    attrs = {
        "srcs": attrs.list(attrs.source(), doc = "Proto source files"),
        "deps": attrs.list(attrs.dep(providers = [ProtoInfo]), doc = "Proto dependencies"),
        "import_prefix": attrs.string(default = "", doc = "Import prefix"),
        "strip_import_prefix": attrs.string(default = "", doc = "Strip import prefix"),
        "options": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Protobuf options"),
        "validation": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Validation config"),
        "well_known_types": attrs.bool(default = True, doc = "Include well-known types"),
        "protoc_version": attrs.string(default = "", doc = "Protoc version"),
    },
)

# Multi-language bundle placeholder - will be implemented in Task 010
def proto_bundle(
    name,
    proto,
    languages,
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Generates code for multiple languages from a single proto_library.
    
    This is a convenience rule that creates multiple language-specific
    generation targets from a single proto library.
    
    Args:
        name: Base name for the bundle (individual targets will be suffixed)
        proto: proto_library target to generate code from
        languages: Dictionary mapping language names to their configurations
        visibility: Buck2 visibility specification applied to all targets
        **kwargs: Additional arguments
    
    Generated Targets:
        - {name}_go (if "go" language specified)
        - {name}_python (if "python" language specified)
        - {name}_typescript (if "typescript" language specified)
        - {name}_cpp (if "cpp" language specified)
        - {name}_rust (if "rust" language specified)
    """
    # Placeholder implementation
    pass

# gRPC service placeholder - will be implemented in Task 010  
def grpc_service(
    name,
    proto,
    languages,
    plugins = {},
    visibility = ["//visibility:private"],
    service_config = {},
    **kwargs
):
    """
    Generates gRPC service code with advanced features for specified languages.
    
    Args:
        name: Target name for the service bundle
        proto: proto_library target containing service definitions
        languages: List of languages to generate code for
        plugins: Plugin configurations for advanced features
        visibility: Buck2 visibility specification
        service_config: Service-specific configuration options
        **kwargs: Additional arguments
    """
    # Placeholder implementation
    pass
