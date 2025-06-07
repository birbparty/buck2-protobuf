"""TypeScript protobuf generation rules for Buck2.

This module provides rules for generating TypeScript code from protobuf definitions.
Supports both basic protobuf messages and gRPC-Web client generation with proper
NPM package integration and TypeScript configuration.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo")
load("//rules/private:utils.bzl", "get_proto_import_path")
load("//rules:tools.bzl", "ensure_tools_available", "TOOL_ATTRS", "get_protoc_command")

def typescript_proto_library(
    name: str,
    proto: str,
    npm_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    plugins: list[str] = ["ts"],
    use_grpc_web: bool = False,
    generate_dts: bool = True,
    options: dict[str, str] = {},
    typescript_version: str = "5.0",
    module_type: str = "esm",
    **kwargs
):
    """
    Generates TypeScript code from a proto_library target.
    
    Args:
        name: Unique name for this TypeScript protobuf library target
        proto: proto_library target to generate TypeScript code from
        npm_package: NPM package name override (e.g., "@org/proto-types")
        visibility: Buck2 visibility specification
        plugins: List of protoc plugins to use ["ts", "grpc-web", "ts-proto"]
        use_grpc_web: Generate gRPC-Web browser clients (adds grpc-web plugin)
        generate_dts: Generate TypeScript declaration files
        options: Additional protoc options for TypeScript generation
        typescript_version: Target TypeScript version for generated code
        module_type: Module system to use ("esm", "commonjs", "both")
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        typescript_proto_library(
            name = "user_ts_proto",
            proto = ":user_proto",
            npm_package = "@myorg/user-types",
            plugins = ["ts", "grpc-web"],
            use_grpc_web = True,
            visibility = ["PUBLIC"],
        )
        
    Generated Files:
        - *.ts: TypeScript protobuf message code
        - *.d.ts: TypeScript declaration files (if generate_dts=True)
        - *_grpc_web_pb.js: gRPC-Web client code (if use_grpc_web=True)
        - package.json: NPM package definition
        - tsconfig.json: TypeScript configuration
    """
    # Add grpc-web plugin if requested
    effective_plugins = list(plugins)
    if use_grpc_web and "grpc-web" not in effective_plugins:
        effective_plugins.append("grpc-web")
    
    typescript_proto_library_rule(
        name = name,
        proto = proto,
        npm_package = npm_package,
        visibility = visibility,
        plugins = effective_plugins,
        use_grpc_web = use_grpc_web,
        generate_dts = generate_dts,
        options = options,
        typescript_version = typescript_version,
        module_type = module_type,
        **kwargs
    )

def _resolve_npm_package(ctx, proto_info):
    """
    Resolves the NPM package name for generated TypeScript code.
    
    Priority order:
    1. Explicit npm_package parameter
    2. Generated package based on proto file path
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        String containing the resolved NPM package name
    """
    # 1. Check explicit parameter
    if ctx.attrs.npm_package:
        return ctx.attrs.npm_package
    
    # 2. Generate from proto file path
    if proto_info.proto_files:
        proto_file = proto_info.proto_files[0]
        return _generate_npm_package_from_path(proto_file.short_path)
    
    fail("Could not resolve NPM package name for proto target")

def _generate_npm_package_from_path(proto_path: str) -> str:
    """
    Generates an NPM package name from a proto file path.
    
    Args:
        proto_path: Path to the proto file (e.g., "pkg/user/user.proto")
        
    Returns:
        Generated NPM package name (e.g., "@proto/pkg-user")
    """
    # Remove .proto extension and get directory
    if proto_path.endswith(".proto"):
        proto_path = proto_path[:-6]
    
    # Get directory path and convert to NPM package name
    parts = proto_path.split("/")
    if len(parts) > 1:
        package_name = "-".join(parts[:-1])
        return "@proto/{}".format(package_name)
    else:
        return "@proto/{}".format(parts[0])

def _get_typescript_output_files(ctx, proto_info, npm_package: str):
    """
    Determines the expected TypeScript output files based on proto content and plugins.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        npm_package: Resolved NPM package name
        
    Returns:
        List of expected output file objects
    """
    output_files = []
    
    # Base name from proto files
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # TypeScript message files (generated by ts or ts-proto plugins)
        if "ts" in ctx.attrs.plugins or "ts-proto" in ctx.attrs.plugins:
            ts_file = ctx.actions.declare_output("typescript", "src", base_name + ".ts")
            output_files.append(ts_file)
            
            # TypeScript declaration files
            if ctx.attrs.generate_dts:
                dts_file = ctx.actions.declare_output("typescript", "src", base_name + ".d.ts")
                output_files.append(dts_file)
        
        # gRPC-Web client files (if grpc-web plugin enabled)
        if "grpc-web" in ctx.attrs.plugins:
            grpc_web_file = ctx.actions.declare_output("typescript", "src", base_name + "_grpc_web_pb.js")
            output_files.append(grpc_web_file)
            
            # TypeScript declarations for gRPC-Web
            if ctx.attrs.generate_dts:
                grpc_web_dts_file = ctx.actions.declare_output("typescript", "src", base_name + "_grpc_web_pb.d.ts")
                output_files.append(grpc_web_dts_file)
    
    # NPM package files
    package_json_file = ctx.actions.declare_output("typescript", "package.json")
    output_files.append(package_json_file)
    
    tsconfig_file = ctx.actions.declare_output("typescript", "tsconfig.json")
    output_files.append(tsconfig_file)
    
    # Main index file
    index_ts_file = ctx.actions.declare_output("typescript", "src", "index.ts")
    output_files.append(index_ts_file)
    
    return output_files

def _create_package_json_content(npm_package: str, module_type: str) -> str:
    """
    Creates package.json file content for generated TypeScript code.
    
    Args:
        npm_package: NPM package name
        module_type: Module system ("esm", "commonjs", "both")
        
    Returns:
        String content for package.json file
    """
    # Base package configuration
    package_config = {
        "name": npm_package,
        "version": "1.0.0",
        "description": "Generated TypeScript protobuf types",
        "main": "dist/index.js",
        "types": "dist/index.d.ts",
        "files": ["dist/**/*"],
        "scripts": {
            "build": "tsc",
            "clean": "rm -rf dist",
            "prepublishOnly": "npm run clean && npm run build"
        },
        "dependencies": {
            "google-protobuf": "^3.21.0"
        },
        "devDependencies": {
            "typescript": "^5.0.0",
            "@types/google-protobuf": "^3.15.0"
        },
        "engines": {
            "node": ">=16.0.0"
        }
    }
    
    # Configure module type
    if module_type == "esm":
        package_config["type"] = "module"
        package_config["exports"] = {
            ".": {
                "types": "./dist/index.d.ts",
                "import": "./dist/index.js"
            }
        }
    elif module_type == "commonjs":
        package_config["exports"] = {
            ".": {
                "types": "./dist/index.d.ts",
                "require": "./dist/index.js"
            }
        }
    elif module_type == "both":
        package_config["exports"] = {
            ".": {
                "types": "./dist/index.d.ts",
                "import": "./dist/index.js",
                "require": "./dist/index.js"
            }
        }
    
    # Add gRPC-Web dependencies if needed
    # This will be set during rule execution based on actual plugins used
    
    return json.encode_indent(package_config, indent = "  ")

def _create_tsconfig_json_content(module_type: str, typescript_version: str) -> str:
    """
    Creates tsconfig.json file content for TypeScript compilation.
    
    Args:
        module_type: Module system to target
        typescript_version: TypeScript version to target
        
    Returns:
        String content for tsconfig.json file
    """
    # Base TypeScript configuration
    tsconfig = {
        "compilerOptions": {
            "target": "ES2020",
            "lib": ["ES2020", "DOM"],
            "moduleResolution": "node",
            "strict": True,
            "esModuleInterop": True,
            "skipLibCheck": True,
            "forceConsistentCasingInFileNames": True,
            "declaration": True,
            "declarationMap": True,
            "sourceMap": True,
            "outDir": "dist",
            "rootDir": "src",
            "removeComments": False,
            "noImplicitReturns": True,
            "noFallthroughCasesInSwitch": True,
            "noUncheckedIndexedAccess": True
        },
        "include": ["src/**/*"],
        "exclude": ["node_modules", "dist"]
    }
    
    # Configure module system
    if module_type == "esm":
        tsconfig["compilerOptions"]["module"] = "ESNext"
        tsconfig["compilerOptions"]["moduleResolution"] = "bundler"
    elif module_type == "commonjs":
        tsconfig["compilerOptions"]["module"] = "CommonJS"
    elif module_type == "both":
        tsconfig["compilerOptions"]["module"] = "ESNext"
        tsconfig["compilerOptions"]["moduleResolution"] = "bundler"
    
    return json.encode_indent(tsconfig, indent = "  ")

def _create_index_ts_content(proto_info) -> str:
    """
    Creates the main index.ts file that exports all generated types.
    
    Args:
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        String content for index.ts file
    """
    exports = []
    
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # Export all types from each generated file
        exports.append("export * from './{}';".format(base_name))
    
    return "\n".join([
        "// Generated TypeScript protobuf exports",
        "// This file is automatically generated. Do not edit manually.",
        "",
    ] + exports + [""])

def _generate_typescript_code(ctx, proto_info, tools, output_files, npm_package: str):
    """
    Executes protoc with TypeScript plugins to generate TypeScript code.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        tools: Dictionary of tool file objects
        output_files: List of expected output files
        npm_package: Resolved NPM package name
    """
    # Create output directory
    output_dir = ctx.actions.declare_output("typescript")
    src_dir = ctx.actions.declare_output("typescript", "src")
    
    # Build protoc command arguments
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths (current + transitive)
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure TypeScript code generation based on plugins
    if "ts" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-ts={}".format(tools["protoc-gen-ts"]))
        protoc_cmd.add("--ts_out={}".format(src_dir.as_output()))
        
        # Add TypeScript-specific options
        ts_options = []
        if ctx.attrs.generate_dts:
            ts_options.append("generate_dts=true")
        
        for opt_key, opt_value in ctx.attrs.options.items():
            if opt_key.startswith("ts_"):
                ts_options.append("{}={}".format(opt_key[3:], opt_value))
        
        if ts_options:
            protoc_cmd.add("--ts_opt={}".format(",".join(ts_options)))
    
    # Configure ts-proto generation (alternative TypeScript generator)
    if "ts-proto" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-ts_proto={}".format(tools["ts-proto"]))
        protoc_cmd.add("--ts_proto_out={}".format(src_dir.as_output()))
        
        # ts-proto specific options
        ts_proto_options = []
        if ctx.attrs.module_type == "esm":
            ts_proto_options.append("esModuleInterop=true")
        
        for opt_key, opt_value in ctx.attrs.options.items():
            if opt_key.startswith("ts_proto_"):
                ts_proto_options.append("{}={}".format(opt_key[9:], opt_value))
        
        if ts_proto_options:
            protoc_cmd.add("--ts_proto_opt={}".format(",".join(ts_proto_options)))
    
    # Configure gRPC-Web generation
    if "grpc-web" in ctx.attrs.plugins:
        protoc_cmd.add("--plugin=protoc-gen-grpc-web={}".format(tools["protoc-gen-grpc-web"]))
        protoc_cmd.add("--grpc-web_out=import_style=typescript,mode=grpcwebtext:{}".format(src_dir.as_output()))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect all inputs
    inputs = [tools["protoc"]] + proto_info.proto_files + proto_info.transitive_descriptor_sets
    
    for plugin_name in ctx.attrs.plugins:
        if plugin_name == "ts" and "protoc-gen-ts" in tools:
            inputs.append(tools["protoc-gen-ts"])
        elif plugin_name == "grpc-web" and "protoc-gen-grpc-web" in tools:
            inputs.append(tools["protoc-gen-grpc-web"])
        elif plugin_name == "ts-proto" and "ts-proto" in tools:
            inputs.append(tools["ts-proto"])
    
    # Run protoc to generate TypeScript code
    ctx.actions.run(
        protoc_cmd,
        category = "typescript_protoc",
        identifier = "{}_typescript_generation".format(ctx.label.name),
        inputs = inputs,
        outputs = [output_dir, src_dir] + [f for f in output_files if f.short_path.startswith("typescript/src/")],
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
        local_only = False,
    )

def _create_npm_package_files(ctx, npm_package: str):
    """
    Creates NPM package configuration files.
    
    Args:
        ctx: Buck2 rule context
        npm_package: NPM package name
        
    Returns:
        List of created file objects
    """
    files = []
    
    # Create package.json
    package_json_file = ctx.actions.declare_output("typescript", "package.json")
    package_json_content = _create_package_json_content(npm_package, ctx.attrs.module_type)
    
    ctx.actions.write(
        package_json_file,
        package_json_content,
    )
    files.append(package_json_file)
    
    # Create tsconfig.json
    tsconfig_file = ctx.actions.declare_output("typescript", "tsconfig.json")
    tsconfig_content = _create_tsconfig_json_content(ctx.attrs.module_type, ctx.attrs.typescript_version)
    
    ctx.actions.write(
        tsconfig_file,
        tsconfig_content,
    )
    files.append(tsconfig_file)
    
    return files

def _create_index_file(ctx, proto_info):
    """
    Creates the main index.ts export file.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        File object for the created index.ts file
    """
    index_ts_file = ctx.actions.declare_output("typescript", "src", "index.ts")
    index_content = _create_index_ts_content(proto_info)
    
    ctx.actions.write(
        index_ts_file,
        index_content,
    )
    
    return index_ts_file

def _typescript_proto_library_impl(ctx):
    """
    Implementation function for typescript_proto_library rule.
    
    Handles:
    - NPM package name resolution
    - Tool downloading and caching
    - protoc execution with TypeScript plugins
    - NPM package file generation
    - TypeScript configuration
    - Output file management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Resolve NPM package name
    npm_package = _resolve_npm_package(ctx, proto_info)
    
    # Ensure required tools are available
    tools = ensure_tools_available(ctx, "typescript")
    
    # Get expected output files
    output_files = _get_typescript_output_files(ctx, proto_info, npm_package)
    
    # Generate TypeScript code using protoc
    _generate_typescript_code(ctx, proto_info, tools, output_files, npm_package)
    
    # Create NPM package configuration files
    package_files = _create_npm_package_files(ctx, npm_package)
    output_files.extend(package_files)
    
    # Create index.ts file
    index_file = _create_index_file(ctx, proto_info)
    output_files.append(index_file)
    
    # Determine dependencies based on plugins used
    dependencies = ["google-protobuf"]
    if "grpc-web" in ctx.attrs.plugins:
        dependencies.extend(["grpc-web", "@grpc/grpc-js"])
    
    # Create LanguageProtoInfo provider
    language_proto_info = LanguageProtoInfo(
        language = "typescript",
        generated_files = output_files,
        package_name = npm_package,
        dependencies = dependencies,
        compiler_flags = [],
    )
    
    # Return providers
    return [
        DefaultInfo(default_outputs = output_files),
        language_proto_info,
    ]

# TypeScript protobuf library rule definition
typescript_proto_library_rule = rule(
    impl = _typescript_proto_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "npm_package": attrs.string(default = "", doc = "NPM package name override"),
        "plugins": attrs.list(attrs.string(), default = ["ts"], doc = "Protoc plugins to use"),
        "use_grpc_web": attrs.bool(default = False, doc = "Generate gRPC-Web browser clients"),
        "generate_dts": attrs.bool(default = True, doc = "Generate TypeScript declaration files"),
        "options": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Additional protoc options"),
        "typescript_version": attrs.string(default = "5.0", doc = "Target TypeScript version"),
        "module_type": attrs.string(default = "esm", doc = "Module system (esm, commonjs, both)"),
        "_protoc": attrs.exec_dep(default = "//tools:protoc"),
        "_protoc_gen_ts": attrs.exec_dep(default = "//tools:protoc-gen-ts", doc = "TypeScript protoc plugin"),
        "_protoc_gen_grpc_web": attrs.exec_dep(default = "//tools:protoc-gen-grpc-web", doc = "gRPC-Web protoc plugin"),
        "_ts_proto": attrs.exec_dep(default = "//tools:ts-proto", doc = "ts-proto protoc plugin"),
    },
)

# Convenience function for basic TypeScript protobuf generation (messages only)
def typescript_proto_messages(
    name: str,
    proto: str,
    npm_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates only TypeScript protobuf message code (no gRPC services).
    
    This is a convenience wrapper around typescript_proto_library that only
    generates basic protobuf message types, excluding gRPC-Web clients.
    
    Args:
        name: Target name
        proto: proto_library target
        npm_package: NPM package name override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    typescript_proto_library(
        name = name,
        proto = proto,
        npm_package = npm_package,
        visibility = visibility,
        plugins = ["ts"],  # Only basic TypeScript, no gRPC-Web
        use_grpc_web = False,
        **kwargs
    )

# Convenience function for gRPC-Web client generation
def typescript_grpc_web_library(
    name: str,
    proto: str,
    npm_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates TypeScript gRPC-Web browser clients with both messages and service definitions.
    
    This is a convenience wrapper around typescript_proto_library that ensures
    both protobuf messages and gRPC-Web browser clients are generated.
    
    Args:
        name: Target name
        proto: proto_library target (must contain service definitions)
        npm_package: NPM package name override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    typescript_proto_library(
        name = name,
        proto = proto,
        npm_package = npm_package,
        visibility = visibility,
        plugins = ["ts", "grpc-web"],  # Both messages and gRPC-Web clients
        use_grpc_web = True,
        **kwargs
    )
