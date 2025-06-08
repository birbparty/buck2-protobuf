"""Connect framework Buck2 rules for modern RPC development.

This module provides Buck2 rules for the Connect framework, enabling
browser-native RPC with better developer experience than traditional gRPC.

Connect provides:
- Connect-Go: Server and client code generation for Go
- Connect-ES: TypeScript/JavaScript client generation for browsers
- Full gRPC interoperability and migration support
- Simplified API patterns and improved performance
"""

load("@prelude//utils:utils.bzl", "expect")
load("//rules/private:providers.bzl", "ProtoInfo", "ConnectInfo")
load("//tools:buf_toolchain.bzl", "get_protoc_toolchain")

def _get_connect_go_plugin(ctx):
    """Get protoc-gen-connect-go plugin binary."""
    toolchain = get_protoc_toolchain()
    return toolchain.get_plugin("protoc-gen-connect-go", "1.16.2")

def _get_connect_es_plugin(ctx):
    """Get protoc-gen-connect-es plugin binary."""
    toolchain = get_protoc_toolchain()
    return toolchain.get_plugin("protoc-gen-connect-es", "1.6.1")

def _get_protoc_gen_es_plugin(ctx):
    """Get protoc-gen-es plugin for base ES types."""
    toolchain = get_protoc_toolchain()
    return toolchain.get_plugin("protoc-gen-es", "1.10.0")

def _connect_go_library_impl(ctx):
    """Implementation for connect_go_library rule."""
    proto_info = ctx.attrs.proto[ProtoInfo]
    toolchain = get_protoc_toolchain()
    
    # Set up output directory
    output_dir = ctx.actions.declare_output("", dir=True)
    
    # Configure Connect-Go specific options
    go_opt = []
    if ctx.attrs.go_package:
        go_opt.append("module={}".format(ctx.attrs.go_package))
    
    # Enable gRPC compatibility if requested
    if ctx.attrs.grpc_compat:
        go_opt.append("grpc-compat=true")
    
    # Prepare protoc command
    protoc_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-connect-go={}".format(_get_connect_go_plugin(ctx)),
        "--connect-go_out={}".format(output_dir.as_output()),
    ]
    
    if go_opt:
        protoc_cmd.append("--connect-go_opt={}".format(",".join(go_opt)))
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        protoc_cmd.extend(["-I", include_path])
    
    # Add proto files
    protoc_cmd.extend([src.path for src in proto_info.proto_sources])
    
    # Execute protoc
    ctx.actions.run(
        protoc_cmd,
        category = "connect_go",
        identifier = ctx.label.name,
        local_only = True,
    )
    
    # Collect generated Go files
    go_sources = []
    for proto_src in proto_info.proto_sources:
        # Connect generates .connect.go files
        base_name = proto_src.basename.removesuffix(".proto")
        go_file = output_dir.project("{}.connect.go".format(base_name))
        go_sources.append(go_file)
    
    return [
        DefaultInfo(default_output = output_dir),
        ConnectInfo(
            language = "go",
            framework = "connect",
            sources = go_sources,
            proto_info = proto_info,
            grpc_compat = ctx.attrs.grpc_compat,
        ),
    ]

def _connect_es_library_impl(ctx):
    """Implementation for connect_es_library rule."""
    proto_info = ctx.attrs.proto[ProtoInfo]
    toolchain = get_protoc_toolchain()
    
    # Set up output directories  
    es_output_dir = ctx.actions.declare_output("es", dir=True)
    connect_output_dir = ctx.actions.declare_output("connect", dir=True)
    
    # Generate base ES types first
    es_protoc_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-es={}".format(_get_protoc_gen_es_plugin(ctx)),
        "--es_out={}".format(es_output_dir.as_output()),
        "--es_opt=target={}".format(ctx.attrs.target),
    ]
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        es_protoc_cmd.extend(["-I", include_path])
    
    # Add proto files
    es_protoc_cmd.extend([src.path for src in proto_info.proto_sources])
    
    # Execute protoc for ES types
    ctx.actions.run(
        es_protoc_cmd,
        category = "protoc_gen_es",
        identifier = "{}_es".format(ctx.label.name),
        local_only = True,
    )
    
    # Generate Connect client code
    connect_protoc_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-connect-es={}".format(_get_connect_es_plugin(ctx)),
        "--connect-es_out={}".format(connect_output_dir.as_output()),
        "--connect-es_opt=target={}".format(ctx.attrs.target),
    ]
    
    # Configure transport if specified
    if ctx.attrs.transport:
        connect_protoc_cmd.append("--connect-es_opt=transport={}".format(ctx.attrs.transport))
    
    # Enable import style configuration
    if ctx.attrs.import_style:
        connect_protoc_cmd.append("--connect-es_opt=import_style={}".format(ctx.attrs.import_style))
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        connect_protoc_cmd.extend(["-I", include_path])
    
    # Add proto files
    connect_protoc_cmd.extend([src.path for src in proto_info.proto_sources])
    
    # Execute protoc for Connect client
    ctx.actions.run(
        connect_protoc_cmd,
        category = "connect_es",
        identifier = "{}_connect".format(ctx.label.name),
        local_only = True,
    )
    
    # Collect generated TypeScript/JavaScript files
    ts_sources = []
    connect_sources = []
    
    for proto_src in proto_info.proto_sources:
        base_name = proto_src.basename.removesuffix(".proto")
        
        if ctx.attrs.target == "ts":
            # TypeScript outputs
            es_file = es_output_dir.project("{}_pb.ts".format(base_name))
            connect_file = connect_output_dir.project("{}_connect.ts".format(base_name))
        else:
            # JavaScript outputs
            es_file = es_output_dir.project("{}_pb.js".format(base_name))
            connect_file = connect_output_dir.project("{}_connect.js".format(base_name))
        
        ts_sources.append(es_file)
        connect_sources.append(connect_file)
    
    # Combine outputs
    all_sources = ts_sources + connect_sources
    combined_output = ctx.actions.declare_output("", dir=True)
    
    # Copy all generated files to combined output
    copy_cmd = ["cp", "-r"] + [es_output_dir.as_output(), connect_output_dir.as_output()] + [combined_output.as_output()]
    ctx.actions.run(
        copy_cmd,
        category = "connect_es_combine",
        identifier = "{}_combine".format(ctx.label.name),
        local_only = True,
    )
    
    return [
        DefaultInfo(default_output = combined_output),
        ConnectInfo(
            language = ctx.attrs.target,
            framework = "connect-es",
            sources = all_sources,
            proto_info = proto_info,
            transport = ctx.attrs.transport,
            import_style = ctx.attrs.import_style,
        ),
    ]

def _connect_service_impl(ctx):
    """Implementation for connect_service rule supporting multiple frameworks."""
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    outputs = {}
    framework_infos = []
    
    # Generate Connect-Go if requested
    if "connect-go" in ctx.attrs.frameworks:
        connect_go_output = ctx.actions.declare_output("connect-go", dir=True)
        
        # Use connect_go_library logic
        connect_go_info = _generate_connect_go(ctx, proto_info, connect_go_output)
        outputs["connect-go"] = connect_go_output
        framework_infos.append(connect_go_info)
    
    # Generate Connect-ES if requested
    if "connect-es" in ctx.attrs.frameworks:
        connect_es_output = ctx.actions.declare_output("connect-es", dir=True)
        
        # Use connect_es_library logic
        connect_es_info = _generate_connect_es(ctx, proto_info, connect_es_output)
        outputs["connect-es"] = connect_es_output
        framework_infos.append(connect_es_info)
    
    # Generate traditional gRPC if requested for compatibility
    if "grpc" in ctx.attrs.frameworks:
        grpc_output = ctx.actions.declare_output("grpc", dir=True)
        
        # Generate traditional gRPC code
        grpc_info = _generate_grpc_compat(ctx, proto_info, grpc_output)
        outputs["grpc"] = grpc_output
        framework_infos.append(grpc_info)
    
    # Create combined output
    combined_output = ctx.actions.declare_output("", dir=True)
    
    # Copy all framework outputs to combined directory
    copy_cmd = ["mkdir", "-p", combined_output.as_output()]
    for framework, output in outputs.items():
        copy_cmd.extend(["&&", "cp", "-r", output.as_output(), combined_output.as_output() + "/" + framework])
    
    ctx.actions.run(
        copy_cmd,
        category = "connect_service_combine",
        identifier = ctx.label.name,
        local_only = True,
    )
    
    return [
        DefaultInfo(default_output = combined_output),
        ConnectInfo(
            language = "multi",
            framework = "connect-service",
            sources = [],
            proto_info = proto_info,
            frameworks = ctx.attrs.frameworks,
            framework_infos = framework_infos,
        ),
    ]

def _generate_connect_go(ctx, proto_info, output_dir):
    """Generate Connect-Go code."""
    toolchain = get_protoc_toolchain()
    
    protoc_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-connect-go={}".format(_get_connect_go_plugin(ctx)),
        "--connect-go_out={}".format(output_dir.as_output()),
    ]
    
    # Add go package configuration
    connect_config = ctx.attrs.connect_config or {}
    if "go_package" in connect_config:
        protoc_cmd.append("--connect-go_opt=module={}".format(connect_config["go_package"]))
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        protoc_cmd.extend(["-I", include_path])
    
    # Add proto files
    protoc_cmd.extend([src.path for src in proto_info.proto_sources])
    
    ctx.actions.run(
        protoc_cmd,
        category = "connect_go_service",
        identifier = "{}_connect_go".format(ctx.label.name),
        local_only = True,
    )
    
    return ConnectInfo(
        language = "go",
        framework = "connect-go",
        sources = [],
        proto_info = proto_info,
    )

def _generate_connect_es(ctx, proto_info, output_dir):
    """Generate Connect-ES code."""
    toolchain = get_protoc_toolchain()
    
    # Generate base ES types
    es_dir = ctx.actions.declare_output("es_temp", dir=True)
    es_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-es={}".format(_get_protoc_gen_es_plugin(ctx)),
        "--es_out={}".format(es_dir.as_output()),
        "--es_opt=target=ts",
    ]
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        es_cmd.extend(["-I", include_path])
    
    # Add proto files
    es_cmd.extend([src.path for src in proto_info.proto_sources])
    
    ctx.actions.run(
        es_cmd,
        category = "es_types_service",
        identifier = "{}_es_types".format(ctx.label.name),
        local_only = True,
    )
    
    # Generate Connect client
    connect_cmd = [
        toolchain.protoc[RunInfo],
        "--plugin=protoc-gen-connect-es={}".format(_get_connect_es_plugin(ctx)),
        "--connect-es_out={}".format(output_dir.as_output()),
        "--connect-es_opt=target=ts",
    ]
    
    # Add Connect-ES configuration
    connect_config = ctx.attrs.connect_config or {}
    if "transport" in connect_config:
        connect_cmd.append("--connect-es_opt=transport={}".format(connect_config["transport"]))
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        connect_cmd.extend(["-I", include_path])
    
    # Add proto files
    connect_cmd.extend([src.path for src in proto_info.proto_sources])
    
    ctx.actions.run(
        connect_cmd,
        category = "connect_es_service",
        identifier = "{}_connect_es".format(ctx.label.name),
        local_only = True,
    )
    
    return ConnectInfo(
        language = "typescript",
        framework = "connect-es",
        sources = [],
        proto_info = proto_info,
    )

def _generate_grpc_compat(ctx, proto_info, output_dir):
    """Generate traditional gRPC code for compatibility."""
    toolchain = get_protoc_toolchain()
    
    # For now, generate basic Go gRPC as compatibility example
    protoc_cmd = [
        toolchain.protoc[RunInfo],
        "--go_out={}".format(output_dir.as_output()),
        "--go-grpc_out={}".format(output_dir.as_output()),
    ]
    
    # Add gRPC configuration
    grpc_config = ctx.attrs.grpc_config or {}
    if "go_package" in grpc_config:
        protoc_cmd.append("--go_opt=module={}".format(grpc_config["go_package"]))
        protoc_cmd.append("--go-grpc_opt=module={}".format(grpc_config["go_package"]))
    
    # Add proto include paths
    for include_path in proto_info.transitive_proto_paths:
        protoc_cmd.extend(["-I", include_path])
    
    # Add proto files
    protoc_cmd.extend([src.path for src in proto_info.proto_sources])
    
    ctx.actions.run(
        protoc_cmd,
        category = "grpc_compat_service",
        identifier = "{}_grpc_compat".format(ctx.label.name),
        local_only = True,
    )
    
    return ConnectInfo(
        language = "go",
        framework = "grpc",
        sources = [],
        proto_info = proto_info,
    )

# Rule definitions
connect_go_library = rule(
    impl = _connect_go_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "proto_library target"),
        "go_package": attrs.option(attrs.string(), doc = "Go package name"),
        "grpc_compat": attrs.bool(default = False, doc = "Enable gRPC compatibility mode"),
    },
    doc = """Generate Connect-Go server and client code.
    
    Connect-Go generates idiomatic Go code for both servers and clients
    with full gRPC interoperability and improved developer experience.
    
    Example:
        connect_go_library(
            name = "user_service_connect",
            proto = ":user_service_proto",
            go_package = "github.com/myorg/user-service",
            grpc_compat = True,
        )
    """,
)

connect_es_library = rule(
    impl = _connect_es_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "proto_library target"),
        "target": attrs.enum(["ts", "js"], default = "ts", doc = "Target language (TypeScript or JavaScript)"),
        "transport": attrs.option(attrs.string(), doc = "Transport protocol (grpc-web, grpc, connect)"),
        "import_style": attrs.option(attrs.string(), doc = "Import style (module, commonjs)"),
    },
    doc = """Generate Connect-ES TypeScript/JavaScript client code.
    
    Connect-ES generates type-safe browser clients with modern JavaScript
    patterns and full Connect protocol support.
    
    Example:
        connect_es_library(
            name = "user_service_web",
            proto = ":user_service_proto",
            target = "ts",
            transport = "grpc-web",
        )
    """,
)

connect_service = rule(
    impl = _connect_service_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "proto_library target"),
        "frameworks": attrs.list(
            attrs.enum(["connect-go", "connect-es", "grpc"]),
            default = ["connect-go"],
            doc = "List of frameworks to generate code for",
        ),
        "connect_config": attrs.option(attrs.dict(key = attrs.string(), value = attrs.string()), doc = "Connect framework configuration"),
        "grpc_config": attrs.option(attrs.dict(key = attrs.string(), value = attrs.string()), doc = "gRPC framework configuration"),
    },
    doc = """Multi-framework service supporting Connect and gRPC.
    
    Generate code for multiple RPC frameworks from a single proto definition,
    enabling gradual migration and framework choice flexibility.
    
    Example:
        connect_service(
            name = "user_service",
            proto = ":user_service_proto",
            frameworks = ["connect-go", "connect-es", "grpc"],
            connect_config = {
                "go_package": "github.com/myorg/user-service",
                "transport": "grpc-web",
            },
            grpc_config = {
                "go_package": "github.com/myorg/user-service/grpc",
            },
        )
    """,
)

# Utility functions for framework selection
def connect_frameworks():
    """Return available Connect frameworks."""
    return ["connect-go", "connect-es"]

def all_frameworks():
    """Return all supported RPC frameworks."""
    return ["connect-go", "connect-es", "grpc"]

def is_connect_framework(framework):
    """Check if a framework is a Connect framework."""
    return framework in connect_frameworks()

# Migration helpers
def migrate_grpc_to_connect(grpc_target, connect_frameworks = ["connect-go"]):
    """Helper to create Connect equivalent of existing gRPC target."""
    return {
        "proto": grpc_target,
        "frameworks": connect_frameworks,
        "grpc_compat": True,
    }
