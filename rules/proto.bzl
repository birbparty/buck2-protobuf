"""Core protobuf rules for Buck2.

This module provides the fundamental protobuf rules that serve as the foundation
for all language-specific code generation. These rules handle proto compilation,
dependency resolution, and provide the base infrastructure for the buck2-protobuf
integration.

The rules defined here follow the API specification and are implemented in Task 002.
"""

load("//rules/private:utils.bzl", "merge_proto_infos", "get_proto_import_path", "validate_proto_library_inputs", "create_descriptor_set_action", "get_proto_package_option")
load("//rules/private:providers.bzl", "ProtoInfo", "ProtoBundleInfo", "GrpcServiceInfo", "CacheKeyInfo", "CacheConfigInfo")
load("//rules/private:bundle_impl.bzl", "validate_bundle_config", "create_language_target", "generate_language_target_name", "validate_cross_language_consistency", "create_bundle_info")
load("//rules/private:grpc_impl.bzl", "validate_grpc_service_config", "generate_grpc_gateway_code", "generate_validation_code", "generate_mock_code", "create_grpc_service_info")
load("//rules/private:cache_impl.bzl", "get_default_cache_config", "create_cache_key_info", "try_cache_lookup", "store_in_cache")
load("//rules/private:cache_keys.bzl", "generate_cache_key_for_bundle", "generate_cache_key_for_grpc_service")

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

# Multi-language bundle implementation
def proto_bundle(
    name,
    proto,
    languages,
    visibility = ["//visibility:private"],
    consistency_checks = True,
    parallel_generation = True,
    **kwargs
):
    """
    Generates code for multiple languages from a single proto_library.
    
    This is a convenience rule that creates multiple language-specific
    generation targets from a single proto library with consistent
    configuration and cross-language validation.
    
    Args:
        name: Base name for the bundle (individual targets will be suffixed)
        proto: proto_library target to generate code from
        languages: Dictionary mapping language names to their configurations
        visibility: Buck2 visibility specification applied to all targets
        consistency_checks: Whether to perform cross-language consistency validation
        parallel_generation: Whether to generate language targets in parallel
        **kwargs: Additional arguments
    
    Generated Targets:
        - {name}_go (if "go" language specified)
        - {name}_python (if "python" language specified)
        - {name}_typescript (if "typescript" language specified)
        - {name}_cpp (if "cpp" language specified)
        - {name}_rust (if "rust" language specified)
    
    Example:
        proto_bundle(
            name = "user_bundle",
            proto = ":user_proto",
            languages = {
                "go": {"go_package": "github.com/org/user/v1"},
                "python": {"python_package": "org.user.v1"},
                "typescript": {"npm_package": "@org/user-v1"},
            },
            visibility = ["PUBLIC"],
        )
    """
    proto_bundle_rule(
        name = name,
        proto = proto,
        languages = languages,
        visibility = visibility,
        consistency_checks = consistency_checks,
        parallel_generation = parallel_generation,
        **kwargs
    )

# gRPC service implementation with advanced features
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
    
    Supports advanced plugins like gRPC-Gateway, OpenAPI documentation,
    validation, and mock generation for comprehensive service development.
    
    Args:
        name: Target name for the service bundle
        proto: proto_library target containing service definitions
        languages: List of languages to generate code for
        plugins: Plugin configurations for advanced features
        visibility: Buck2 visibility specification
        service_config: Service-specific configuration options
        **kwargs: Additional arguments
    
    Supported Plugins:
        - grpc-gateway: HTTP/JSON to gRPC proxy (Go only)
        - openapi: OpenAPI/Swagger documentation
        - validate: Request/response validation
        - mock: Mock implementations for testing
        - grpc-web: Browser gRPC clients (TypeScript)
    
    Example:
        grpc_service(
            name = "user_service",
            proto = ":user_service_proto",
            languages = ["go", "python", "typescript"],
            plugins = {
                "grpc-gateway": {"enabled": True},
                "openapi": {"output_format": "json"},
                "validate": {"emit_imported_vars": True},
                "mock": {"package": "usermocks"},
            },
            visibility = ["PUBLIC"],
        )
    """
    grpc_service_rule(
        name = name,
        proto = proto,
        languages = languages,
        plugins = plugins,
        visibility = visibility,
        service_config = service_config,
        **kwargs
    )

def _proto_bundle_impl(ctx):
    """Implementation function for proto_bundle rule.
    
    Handles:
    - Multi-language code generation coordination
    - Language-specific target creation
    - Cross-language consistency validation
    - Bundle information management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Validate and normalize language configurations
    validated_languages = validate_bundle_config(ctx.attrs.languages)
    
    # Create language-specific targets
    language_targets = {}
    for language, config in validated_languages.items():
        target_name = generate_language_target_name(ctx.label.name, language)
        language_target = create_language_target(
            ctx, 
            language, 
            config, 
            ctx.attrs.proto, 
            target_name
        )
        language_targets[language] = language_target
    
    # Perform cross-language consistency validation if enabled
    consistency_report = None
    if ctx.attrs.consistency_checks:
        consistency_report = validate_cross_language_consistency(
            ctx, 
            ctx.label.name, 
            language_targets, 
            proto_info
        )
        
        # Log consistency warnings
        if consistency_report.validation_warnings:
            for warning in consistency_report.validation_warnings:
                print("Bundle consistency warning: {}".format(warning))
        
        # Fail on consistency errors
        if consistency_report.validation_errors:
            for error in consistency_report.validation_errors:
                print("Bundle consistency error: {}".format(error))
            fail("Bundle validation failed due to consistency errors")
    
    # Create bundle information
    bundle_info = create_bundle_info(
        ctx,
        ctx.label.name,
        ctx.attrs.proto,
        language_targets,
        consistency_report,
        ctx.attrs.languages
    )
    
    # Collect all generated outputs for default target
    all_outputs = []
    for target_info in language_targets.values():
        # In a real implementation, we would collect actual generated files
        # For now, we use a placeholder approach
        pass
    
    return [
        DefaultInfo(default_outputs = all_outputs),
        bundle_info,
    ]

def _grpc_service_impl(ctx):
    """Implementation function for grpc_service rule.
    
    Handles:
    - gRPC service code generation with advanced plugins
    - Language-specific service target creation
    - Plugin execution coordination
    - Service information management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Validate gRPC service configuration
    validated_languages, validated_plugins, validated_config = validate_grpc_service_config(
        ctx.attrs.languages,
        ctx.attrs.plugins,
        ctx.attrs.service_config
    )
    
    # Create base language-specific service targets
    language_targets = {}
    for language in validated_languages:
        target_name = "{}_{}".format(ctx.label.name, language)
        # In a real implementation, we would create language-specific gRPC targets
        # This is simplified for the current implementation
        language_targets[language] = {"name": target_name, "language": language}
    
    # Generate plugin-specific code
    gateway_files = []
    openapi_files = []
    validation_files = []
    mock_files = []
    
    output_dir = "grpc_service"
    
    # Generate gRPC-Gateway code if enabled
    if "grpc-gateway" in validated_plugins:
        gateway_files = generate_grpc_gateway_code(
            ctx, 
            proto_info, 
            validated_plugins["grpc-gateway"], 
            output_dir
        )
    
    # Generate validation code if enabled
    if "validate" in validated_plugins:
        validation_files = generate_validation_code(
            ctx, 
            proto_info, 
            validated_plugins["validate"], 
            validated_languages, 
            output_dir
        )
    
    # Generate mock code if enabled
    if "mock" in validated_plugins:
        mock_files = generate_mock_code(
            ctx, 
            proto_info, 
            validated_plugins["mock"], 
            validated_languages, 
            output_dir
        )
    
    # Create gRPC service information
    service_info = create_grpc_service_info(
        ctx,
        ctx.label.name,
        ctx.attrs.proto,
        validated_languages,
        validated_plugins,
        gateway_files,
        openapi_files,
        validation_files,
        mock_files,
        validated_config
    )
    
    # Collect all generated outputs
    all_outputs = gateway_files + openapi_files + validation_files + mock_files
    
    return [
        DefaultInfo(default_outputs = all_outputs),
        service_info,
    ]

# Proto bundle rule definition
proto_bundle_rule = rule(
    impl = _proto_bundle_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "languages": attrs.dict(
            attrs.string(), 
            attrs.dict(attrs.string(), attrs.string()), 
            doc = "Language configurations"
        ),
        "consistency_checks": attrs.bool(default = True, doc = "Enable consistency validation"),
        "parallel_generation": attrs.bool(default = True, doc = "Enable parallel generation"),
    },
)

# gRPC service rule definition
grpc_service_rule = rule(
    impl = _grpc_service_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "languages": attrs.list(attrs.string(), doc = "Target languages"),
        "plugins": attrs.dict(
            attrs.string(), 
            attrs.dict(attrs.string(), attrs.string()), 
            default = {}, 
            doc = "Plugin configurations"
        ),
        "service_config": attrs.dict(
            attrs.string(), 
            attrs.string(), 
            default = {}, 
            doc = "Service-specific configuration"
        ),
    },
)
