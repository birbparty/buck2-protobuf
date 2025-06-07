"""Rust protobuf generation rules for Buck2.

This module provides rules for generating Rust code from protobuf definitions.
Supports both basic protobuf messages (prost) and gRPC services (tonic) with 
proper Cargo integration, async/await support, and modern Rust features.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo")
load("//rules/private:utils.bzl", "get_proto_import_path")
load("//rules:tools.bzl", "ensure_tools_available", "TOOL_ATTRS", "get_protoc_command")

def rust_proto_library(
    name: str,
    proto: str,
    rust_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    plugins: list[str] = ["prost"],
    features: list[str] = [],
    options: dict[str, str] = {},
    derive: list[str] = [],
    use_grpc: bool = False,
    edition: str = "2021",
    serde: bool = False,
    **kwargs
):
    """
    Generates Rust code from a proto_library target.
    
    Args:
        name: Unique name for this Rust protobuf library target
        proto: proto_library target to generate Rust code from
        rust_package: Rust package/crate name (e.g., "user_proto")
        visibility: Buck2 visibility specification
        plugins: List of protoc plugins to use ["prost", "tonic"]
        features: List of Cargo features to enable
        options: Additional protoc options for Rust generation
        derive: Additional derive macros for generated structs
        use_grpc: Generate tonic gRPC service code (adds tonic plugin)
        edition: Rust edition to use (2018, 2021)
        serde: Enable serde serialization support
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        rust_proto_library(
            name = "user_rust_proto",
            proto = ":user_proto",
            rust_package = "user_proto",
            plugins = ["prost", "tonic"],
            use_grpc = True,
            serde = True,
            derive = ["Clone", "Debug"],
            visibility = ["PUBLIC"],
        )
        
    Generated Files:
        - Cargo.toml: Rust package configuration
        - src/lib.rs: Library root with module exports
        - src/*.rs: Generated Rust code for protobuf messages and services
    """
    # Add tonic plugin if requested
    effective_plugins = list(plugins)
    if use_grpc and "tonic" not in effective_plugins:
        effective_plugins.append("tonic")
    
    # Enable serde feature if requested
    effective_features = list(features)
    if serde and "serde" not in effective_features:
        effective_features.append("serde")
    
    rust_proto_library_rule(
        name = name,
        proto = proto,
        rust_package = rust_package,
        visibility = visibility,
        plugins = effective_plugins,
        features = effective_features,
        options = options,
        derive = derive,
        use_grpc = use_grpc,
        edition = edition,
        serde = serde,
        **kwargs
    )

def _resolve_rust_package(ctx, proto_info):
    """
    Resolves the Rust package name for generated code.
    
    Priority order:
    1. Explicit rust_package parameter
    2. Generated package name based on proto file path
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        String containing the resolved Rust package name
    """
    # 1. Check explicit parameter
    if ctx.attrs.rust_package:
        return ctx.attrs.rust_package
    
    # 2. Generate from proto file path
    if proto_info.proto_files:
        proto_file = proto_info.proto_files[0]
        return _generate_package_from_path(proto_file.short_path)
    
    # 3. Fallback to target name
    return ctx.label.name.replace("-", "_")

def _generate_package_from_path(proto_path: str) -> str:
    """
    Generates a Rust package name from a proto file path.
    
    Args:
        proto_path: Path to the proto file (e.g., "pkg/user/user.proto")
        
    Returns:
        Generated Rust package name (e.g., "pkg_user_proto")
    """
    # Remove .proto extension and get directory + filename
    if proto_path.endswith(".proto"):
        proto_path = proto_path[:-6]
    
    # Replace path separators and hyphens with underscores
    package_name = proto_path.replace("/", "_").replace("-", "_")
    
    # Add _proto suffix if not already present
    if not package_name.endswith("_proto"):
        package_name += "_proto"
    
    return package_name

def _get_rust_output_files(ctx, proto_info):
    """
    Determines the expected Rust output files based on proto content and plugins.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        List of expected output file objects
    """
    output_files = []
    
    # Base name from proto files
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # Convert to snake_case for Rust modules
        rust_module = base_name.replace("-", "_").lower()
        
        # Rust protobuf files (generated by prost plugin)
        if "prost" in ctx.attrs.plugins:
            rust_file = ctx.actions.declare_output("rust", "src", rust_module + ".rs")
            output_files.append(rust_file)
        
        # tonic gRPC service files (if tonic plugin enabled)
        if "tonic" in ctx.attrs.plugins:
            # Tonic generates services in the same files as messages
            # but we may need separate service-specific files for complex cases
            if base_name.endswith("_service") or "service" in base_name.lower():
                service_file = ctx.actions.declare_output("rust", "src", rust_module + "_service.rs")
                output_files.append(service_file)
    
    # Library configuration files
    cargo_toml = ctx.actions.declare_output("rust", "Cargo.toml")
    output_files.append(cargo_toml)
    
    lib_rs = ctx.actions.declare_output("rust", "src", "lib.rs")
    output_files.append(lib_rs)
    
    # Build script (optional, for additional codegen)
    build_rs = ctx.actions.declare_output("rust", "build.rs")
    output_files.append(build_rs)
    
    return output_files

def _create_cargo_toml_content(ctx, rust_package: str) -> str:
    """
    Creates Cargo.toml content for generated Rust code.
    
    Args:
        ctx: Buck2 rule context
        rust_package: Rust package name
        
    Returns:
        String content for Cargo.toml file
    """
    # Base dependencies
    dependencies = {
        "prost": "0.12",
    }
    
    # Add tonic dependencies if needed
    if "tonic" in ctx.attrs.plugins:
        dependencies.update({
            "tonic": "0.10",
            "tokio": {"version": "1.0", "features": ["macros", "rt-multi-thread"]},
        })
    
    # Add serde if enabled
    if ctx.attrs.serde:
        dependencies["serde"] = {"version": "1.0", "features": ["derive"]}
    
    # Build dependencies section
    deps_lines = []
    for dep, version in dependencies.items():
        if isinstance(version, dict):
            # Complex dependency specification
            features_str = ", ".join([f'"{f}"' for f in version.get("features", [])])
            if features_str:
                deps_lines.append(f'{dep} = {{ version = "{version["version"]}", features = [{features_str}] }}')
            else:
                deps_lines.append(f'{dep} = "{version["version"]}"')
        else:
            # Simple version string
            deps_lines.append(f'{dep} = "{version}"')
    
    # Optional dependencies (for features)
    optional_deps = []
    if ctx.attrs.serde:
        # serde is already added above, but mark it as optional if it's a feature
        pass
    
    # Features section
    features_lines = ["default = []"]
    if ctx.attrs.serde:
        features_lines.append('serde = ["dep:serde"]')
    
    # Add custom features
    for feature in ctx.attrs.features:
        if feature not in ["serde"]:  # Don't duplicate built-in features
            features_lines.append(f'"{feature}" = []')
    
    return f'''[package]
name = "{rust_package}"
version = "0.1.0"
edition = "{ctx.attrs.edition}"

[dependencies]
{chr(10).join(deps_lines)}

[features]
{chr(10).join(features_lines)}

# Generated by Buck2 protobuf rules
# This file can be customized as needed for your project
'''

def _create_lib_rs_content(ctx, proto_info, rust_package: str) -> str:
    """
    Creates lib.rs content for generated Rust library.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        rust_package: Rust package name
        
    Returns:
        String content for lib.rs file
    """
    # Collect module names from proto files
    modules = []
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        rust_module = base_name.replace("-", "_").lower()
        modules.append(rust_module)
    
    # Generate module declarations and re-exports
    module_lines = []
    export_lines = []
    
    for module in modules:
        module_lines.append(f"pub mod {module};")
        export_lines.append(f"pub use {module}::*;")
    
    # Add tonic imports if gRPC is enabled
    tonic_imports = ""
    if "tonic" in ctx.attrs.plugins:
        tonic_imports = """
// Re-export tonic for convenient access
pub use tonic;
"""
    
    return f'''//! Generated protobuf library: {rust_package}
//! 
//! This library contains generated Rust code from protobuf definitions.
//! Generated by Buck2 protobuf rules.

{chr(10).join(module_lines)}

// Re-export all generated types for convenient access
{chr(10).join(export_lines)}
{tonic_imports}
'''

def _create_build_rs_content(ctx) -> str:
    """
    Creates build.rs content for additional build-time codegen.
    
    Args:
        ctx: Buck2 rule context
        
    Returns:
        String content for build.rs file
    """
    return '''//! Build script for additional protobuf codegen
//! 
//! This build script can be used for additional code generation
//! or build-time configuration if needed.

fn main() {
    // Additional build logic can go here
    // For example, generating additional derive implementations
    // or setting up build-time environment variables
    
    println!("cargo:rerun-if-changed=build.rs");
}
'''

def _generate_rust_code(ctx, proto_info, tools, output_files, rust_package: str):
    """
    Executes protoc with Rust plugins to generate Rust code.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        tools: Dictionary of tool file objects
        output_files: List of expected output files
        rust_package: Resolved Rust package name
    """
    # Create output directory
    output_dir = ctx.actions.declare_output("rust")
    src_dir = ctx.actions.declare_output("rust", "src")
    
    # Build protoc command arguments
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths (current + transitive)
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure prost code generation
    if "prost" in ctx.attrs.plugins:
        protoc_cmd.add("--prost_out={}".format(src_dir.as_output()))
        
        # Add prost-specific options
        prost_options = []
        
        # Add derive macros
        if ctx.attrs.derive:
            derive_list = ",".join(ctx.attrs.derive)
            prost_options.append(f"derive={derive_list}")
        
        # Add serde support
        if ctx.attrs.serde:
            prost_options.append("serde")
        
        # Add custom options
        for opt_key, opt_value in ctx.attrs.options.items():
            if opt_key.startswith("prost_"):
                prost_options.append(f"{opt_key[6:]}={opt_value}")
        
        if prost_options:
            protoc_cmd.add("--prost_opt={}".format(",".join(prost_options)))
    
    # Configure tonic gRPC generation
    if "tonic" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-tonic={}".format(tools["protoc-gen-tonic"]))
        protoc_cmd.add("--tonic_out={}".format(src_dir.as_output()))
        
        # Add tonic-specific options
        tonic_options = ["compile_well_known_types"]  # Always enable well-known types
        
        for opt_key, opt_value in ctx.attrs.options.items():
            if opt_key.startswith("tonic_"):
                tonic_options.append(f"{opt_key[6:]}={opt_value}")
        
        if tonic_options:
            protoc_cmd.add("--tonic_opt={}".format(",".join(tonic_options)))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect all inputs
    inputs = [tools["protoc"]] + proto_info.proto_files + proto_info.transitive_descriptor_sets
    
    # Add plugin binaries if available
    if "tonic" in ctx.attrs.plugins and "protoc-gen-tonic" in tools:
        inputs.append(tools["protoc-gen-tonic"])
    
    # Run protoc to generate Rust code
    ctx.actions.run(
        protoc_cmd,
        category = "rust_protoc",
        identifier = "{}_rust_generation".format(ctx.label.name),
        inputs = inputs,
        outputs = [output_dir, src_dir] + [f for f in output_files if f.short_path.startswith("rust/src/") and f.short_path.endswith(".rs")],
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
        local_only = False,
    )

def _create_package_config_files(ctx, rust_package: str):
    """
    Creates Rust package configuration files.
    
    Args:
        ctx: Buck2 rule context
        rust_package: Rust package name
        
    Returns:
        List of created file objects
    """
    files = []
    
    # Create Cargo.toml
    cargo_toml = ctx.actions.declare_output("rust", "Cargo.toml")
    cargo_content = _create_cargo_toml_content(ctx, rust_package)
    
    ctx.actions.write(
        cargo_toml,
        cargo_content,
    )
    files.append(cargo_toml)
    
    # Create lib.rs
    lib_rs = ctx.actions.declare_output("rust", "src", "lib.rs")
    proto_info = ctx.attrs.proto[ProtoInfo]
    lib_content = _create_lib_rs_content(ctx, proto_info, rust_package)
    
    ctx.actions.write(
        lib_rs,
        lib_content,
    )
    files.append(lib_rs)
    
    # Create build.rs
    build_rs = ctx.actions.declare_output("rust", "build.rs")
    build_content = _create_build_rs_content(ctx)
    
    ctx.actions.write(
        build_rs,
        build_content,
    )
    files.append(build_rs)
    
    return files

def _rust_proto_library_impl(ctx):
    """
    Implementation function for rust_proto_library rule.
    
    Handles:
    - Rust package name resolution
    - Tool downloading and caching
    - protoc execution with Rust plugins (prost/tonic)
    - Cargo.toml and lib.rs generation
    - Output file management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Resolve Rust package name
    rust_package = _resolve_rust_package(ctx, proto_info)
    
    # Ensure required tools are available
    tools = ensure_tools_available(ctx, "rust")
    
    # Get expected output files
    output_files = _get_rust_output_files(ctx, proto_info)
    
    # Generate Rust code using protoc
    _generate_rust_code(ctx, proto_info, tools, output_files, rust_package)
    
    # Create package configuration files
    config_files = _create_package_config_files(ctx, rust_package)
    output_files.extend(config_files)
    
    # Determine dependencies based on plugins used
    dependencies = ["prost"]
    if "tonic" in ctx.attrs.plugins:
        dependencies.extend(["tonic", "tokio"])
    if ctx.attrs.serde:
        dependencies.append("serde")
    
    # Create LanguageProtoInfo provider
    language_proto_info = LanguageProtoInfo(
        language = "rust",
        generated_files = output_files,
        package_name = rust_package,
        dependencies = dependencies,
        compiler_flags = [],  # Rust doesn't use compiler flags like C++
    )
    
    # Return providers
    return [
        DefaultInfo(default_outputs = output_files),
        language_proto_info,
    ]

# Rust protobuf library rule definition
rust_proto_library_rule = rule(
    impl = _rust_proto_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "rust_package": attrs.string(default = "", doc = "Rust package/crate name"),
        "plugins": attrs.list(attrs.string(), default = ["prost"], doc = "Protoc plugins to use"),
        "features": attrs.list(attrs.string(), default = [], doc = "Cargo features to enable"),
        "options": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Additional protoc options"),
        "derive": attrs.list(attrs.string(), default = [], doc = "Additional derive macros"),
        "use_grpc": attrs.bool(default = False, doc = "Generate tonic gRPC service code"),
        "edition": attrs.string(default = "2021", doc = "Rust edition to use"),
        "serde": attrs.bool(default = False, doc = "Enable serde serialization support"),
        **TOOL_ATTRS
    },
)

# Convenience function for basic Rust protobuf generation (messages only)
def rust_proto_messages(
    name: str,
    proto: str,
    rust_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates only Rust protobuf message code (no gRPC services).
    
    This is a convenience wrapper around rust_proto_library that only
    generates basic protobuf message types using prost, excluding gRPC services.
    
    Args:
        name: Target name
        proto: proto_library target
        rust_package: Rust package/crate name
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    rust_proto_library(
        name = name,
        proto = proto,
        rust_package = rust_package,
        visibility = visibility,
        plugins = ["prost"],  # Only prost, no tonic
        use_grpc = False,
        **kwargs
    )

# Convenience function for tonic gRPC service generation
def rust_grpc_library(
    name: str,
    proto: str,
    rust_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates Rust gRPC services with both messages and service definitions.
    
    This is a convenience wrapper around rust_proto_library that ensures
    both protobuf messages (prost) and gRPC services (tonic) are generated.
    
    Args:
        name: Target name
        proto: proto_library target (must contain service definitions)
        rust_package: Rust package/crate name
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    rust_proto_library(
        name = name,
        proto = proto,
        rust_package = rust_package,
        visibility = visibility,
        plugins = ["prost", "tonic"],  # Both messages and gRPC services
        use_grpc = True,
        **kwargs
    )
