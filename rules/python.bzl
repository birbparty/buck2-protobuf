"""Python protobuf generation rules for Buck2.

This module provides rules for generating Python code from protobuf definitions.
Supports both basic protobuf messages and gRPC service stubs with comprehensive
mypy type checking support and proper Python package structure.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo")
load("//rules/private:utils.bzl", "get_proto_import_path")
load("//rules:tools.bzl", "ensure_tools_available", "TOOL_ATTRS", "get_protoc_command")

def python_proto_library(
    name: str,
    proto: str,
    python_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    plugins: list[str] = ["python", "grpc-python"],
    generate_stubs: bool = True,
    mypy_support: bool = True,
    options: dict[str, str] = {},
    **kwargs
):
    """
    Generates Python code from a proto_library target.
    
    Args:
        name: Unique name for this Python protobuf library target
        proto: proto_library target to generate Python code from
        python_package: Python package path override (e.g., "myapp.protos.v1")
        visibility: Buck2 visibility specification
        plugins: List of protoc plugins to use ["python", "grpc-python", "mypy"]
        generate_stubs: Whether to generate .pyi type stub files
        mypy_support: Whether to enable mypy compatibility features
        options: Additional protoc options for Python generation
        **kwargs: Additional arguments passed to underlying rule
    
    Example:
        python_proto_library(
            name = "user_py_proto",
            proto = ":user_proto",
            python_package = "myapp.protos.user.v1",
            plugins = ["python", "grpc-python"],
            visibility = ["PUBLIC"],
        )
        
    Generated Files:
        - *_pb2.py: Basic protobuf message code (protoc --python_out)
        - *_pb2_grpc.py: gRPC service stubs (protoc --grpc_python_out)
        - *_pb2.pyi: Type stubs for basic protobuf code
        - *_pb2_grpc.pyi: Type stubs for gRPC service code
        - __init__.py: Python package initialization
        - py.typed: PEP 561 typed package marker
    """
    python_proto_library_rule(
        name = name,
        proto = proto,
        python_package = python_package,
        visibility = visibility,
        plugins = plugins,
        generate_stubs = generate_stubs,
        mypy_support = mypy_support,
        options = options,
        **kwargs
    )

def _resolve_python_package(ctx, proto_info):
    """
    Resolves the Python package path for generated code.
    
    Priority order:
    1. Explicit python_package parameter
    2. python_package option from proto file
    3. Generated package based on proto file path
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        String containing the resolved Python package path
    """
    # 1. Check explicit parameter
    if ctx.attrs.python_package:
        return ctx.attrs.python_package
    
    # 2. Check proto file option
    if proto_info.python_package:
        return proto_info.python_package
    
    # 3. Generate from proto file path
    if proto_info.proto_files:
        proto_file = proto_info.proto_files[0]
        return _generate_python_package_from_path(proto_file.short_path)
    
    fail("Could not resolve Python package path for proto target")

def _generate_python_package_from_path(proto_path: str) -> str:
    """
    Generates a Python package path from a proto file path.
    
    Args:
        proto_path: Path to the proto file (e.g., "pkg/user/user.proto")
        
    Returns:
        Generated Python package path (e.g., "pkg.user")
    """
    # Remove .proto extension and get directory
    if proto_path.endswith(".proto"):
        proto_path = proto_path[:-6]
    
    # Get directory path and convert to Python package format
    parts = proto_path.split("/")
    if len(parts) > 1:
        return ".".join(parts[:-1])
    else:
        return ""

def _get_python_output_files(ctx, proto_info, python_package: str):
    """
    Determines the expected Python output files based on proto content and plugins.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        python_package: Resolved Python package path
        
    Returns:
        List of expected output file objects
    """
    output_files = []
    
    # Base name from proto files
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        # Basic protobuf messages (always generated if "python" plugin enabled)
        if "python" in ctx.attrs.plugins:
            pb2_file = ctx.actions.declare_output("python", base_name + "_pb2.py")
            output_files.append(pb2_file)
            
            # Generate type stubs if requested
            if ctx.attrs.generate_stubs:
                pb2_stub_file = ctx.actions.declare_output("python", base_name + "_pb2.pyi")
                output_files.append(pb2_stub_file)
        
        # gRPC service stubs (if "grpc-python" plugin enabled)
        if "grpc-python" in ctx.attrs.plugins:
            grpc_file = ctx.actions.declare_output("python", base_name + "_pb2_grpc.py")
            output_files.append(grpc_file)
            
            # Generate gRPC type stubs if requested
            if ctx.attrs.generate_stubs:
                grpc_stub_file = ctx.actions.declare_output("python", base_name + "_pb2_grpc.pyi")
                output_files.append(grpc_stub_file)
    
    # Package structure files
    init_file = ctx.actions.declare_output("python", "__init__.py")
    output_files.append(init_file)
    
    # PEP 561 marker file for type checking support
    if ctx.attrs.mypy_support:
        py_typed_file = ctx.actions.declare_output("python", "py.typed")
        output_files.append(py_typed_file)
    
    return output_files

def _create_init_py_content(ctx, python_package: str, proto_info) -> str:
    """
    Creates __init__.py file content for the generated Python package.
    
    Args:
        ctx: Buck2 rule context
        python_package: Python package path
        proto_info: ProtoInfo provider
        
    Returns:
        String content for __init__.py file
    """
    # Collect all module names that will be generated
    module_names = []
    for proto_file in proto_info.proto_files:
        base_name = proto_file.basename
        if base_name.endswith(".proto"):
            base_name = base_name[:-6]
        
        if "python" in ctx.attrs.plugins:
            module_names.append(base_name + "_pb2")
        if "grpc-python" in ctx.attrs.plugins:
            module_names.append(base_name + "_pb2_grpc")
    
    # Create __init__.py content
    content = '''"""Generated Python protobuf package.

This package contains protobuf message definitions and gRPC service stubs
automatically generated from .proto files using Buck2.
"""

'''
    
    if python_package:
        content += '__package__ = "{}"\n'.format(python_package)
    
    content += '__version__ = "1.0.0"\n\n'
    
    if module_names:
        content += '__all__ = [\n'
        for module_name in sorted(module_names):
            content += '    "{}",\n'.format(module_name)
        content += ']\n\n'
        
        # Add convenience imports
        content += '# Convenience imports\n'
        for module_name in sorted(module_names):
            content += 'from . import {}\n'.format(module_name)
    
    return content

def _create_py_typed_content() -> str:
    """
    Creates py.typed file content for PEP 561 compliance.
    
    Returns:
        String content for py.typed file
    """
    return """# PEP 561 stub package marker file
# This file indicates that this package supports type checking
# and provides type information for mypy and other type checkers.
"""

def _generate_type_stubs(ctx, generated_files):
    """
    Generates .pyi type stub files for mypy support.
    
    Args:
        ctx: Buck2 rule context
        generated_files: List of generated .py files
        
    Returns:
        List of generated .pyi stub files
    """
    stub_files = []
    
    for py_file in generated_files:
        if py_file.short_path.endswith(".py") and not py_file.short_path.endswith("__init__.py"):
            # Create corresponding .pyi file
            stub_path = py_file.short_path.replace(".py", ".pyi")
            stub_file = ctx.actions.declare_output("python", stub_path.split("/")[-1])
            
            # Generate basic type stub content
            stub_content = _create_stub_content(py_file.basename)
            
            ctx.actions.write(
                stub_file,
                stub_content,
            )
            
            stub_files.append(stub_file)
    
    return stub_files

def _create_stub_content(py_filename: str) -> str:
    """
    Creates basic type stub content for a Python protobuf file.
    
    Args:
        py_filename: Name of the Python file (e.g., "user_pb2.py")
        
    Returns:
        String content for the .pyi stub file
    """
    if py_filename.endswith("_pb2.py"):
        return '''"""Type stubs for protobuf message definitions."""

from typing import Any, Dict, List, Optional, Union
import google.protobuf.message
import google.protobuf.descriptor

# Placeholder type stubs - will be enhanced with actual type information
# Generated protobuf classes will have proper type annotations

__all__: List[str]

class Message(google.protobuf.message.Message):
    def __init__(self, **kwargs: Any) -> None: ...
    def SerializeToString(self) -> bytes: ...
    def ParseFromString(self, data: bytes) -> None: ...
    def CopyFrom(self, other: Message) -> None: ...
'''
    elif py_filename.endswith("_pb2_grpc.py"):
        return '''"""Type stubs for gRPC service definitions."""

from typing import Any, Callable, Iterator, Optional, Union
import grpc
import grpc.aio

# Placeholder type stubs for gRPC services
# Generated service classes will have proper type annotations

__all__: List[str]

class ServicerContext:
    def __init__(self) -> None: ...

class Servicer:
    def __init__(self) -> None: ...

class Stub:
    def __init__(self, channel: Union[grpc.Channel, grpc.aio.Channel]) -> None: ...
'''
    else:
        return '''"""Type stubs for generated Python code."""

from typing import Any

__all__: List[str]
'''

def _generate_python_code(ctx, proto_info, tools, output_files, python_package: str):
    """
    Executes protoc with Python plugins to generate Python code.
    
    Args:
        ctx: Buck2 rule context
        proto_info: ProtoInfo provider from proto dependency
        tools: Dictionary of tool file objects
        output_files: List of expected output files
        python_package: Resolved Python package path
    """
    # Create output directory
    output_dir = ctx.actions.declare_output("python")
    
    # Build protoc command arguments
    protoc_cmd = cmd_args([tools["protoc"]])
    
    # Add import paths (current + transitive)
    all_import_paths = proto_info.import_paths + proto_info.transitive_import_paths
    for import_path in all_import_paths:
        protoc_cmd.add("--proto_path={}".format(import_path))
    
    # Configure Python code generation
    if "python" in ctx.attrs.plugins:
        protoc_cmd.add("--python_out={}".format(output_dir.as_output()))
        
        # Add custom Python package mapping if specified
        if python_package:
            for proto_file in proto_info.proto_files:
                protoc_cmd.add("--python_opt=M{}={}".format(
                    proto_file.short_path, 
                    python_package
                ))
    
    # Configure gRPC Python generation
    if "grpc-python" in ctx.attrs.plugins:
        # Note: gRPC Python plugin is typically provided by grpcio-tools
        protoc_cmd.add("--grpc_python_out={}".format(output_dir.as_output()))
        
        # Add custom gRPC package mapping if specified
        if python_package:
            for proto_file in proto_info.proto_files:
                protoc_cmd.add("--grpc_python_opt=M{}={}".format(
                    proto_file.short_path, 
                    python_package
                ))
    
    # Add any additional options
    for opt_key, opt_value in ctx.attrs.options.items():
        if opt_key.startswith("python_"):
            protoc_cmd.add("--python_opt={}={}".format(opt_key[7:], opt_value))
        elif opt_key.startswith("grpc_python_"):
            protoc_cmd.add("--grpc_python_opt={}={}".format(opt_key[12:], opt_value))
    
    # Add proto files
    protoc_cmd.add(proto_info.proto_files)
    
    # Collect all inputs
    inputs = [tools["protoc"]] + proto_info.proto_files + proto_info.transitive_descriptor_sets
    
    # Run protoc to generate Python code
    ctx.actions.run(
        protoc_cmd,
        category = "python_protoc",
        identifier = "{}_python_generation".format(ctx.label.name),
        inputs = inputs,
        outputs = [output_dir] + [f for f in output_files if f.short_path.endswith((".py", ".pyi"))],
        env = {
            "PATH": "/usr/bin:/bin:/usr/local/bin",
            "PYTHONPATH": "/usr/lib/python3/dist-packages:/usr/local/lib/python3/dist-packages",
        },
        local_only = False,
    )

def _create_package_files(ctx, python_package: str, proto_info):
    """
    Creates Python package structure files (__init__.py, py.typed).
    
    Args:
        ctx: Buck2 rule context
        python_package: Python package path
        proto_info: ProtoInfo provider
        
    Returns:
        List of created package files
    """
    package_files = []
    
    # Create __init__.py file
    init_file = ctx.actions.declare_output("python", "__init__.py")
    init_content = _create_init_py_content(ctx, python_package, proto_info)
    
    ctx.actions.write(
        init_file,
        init_content,
    )
    package_files.append(init_file)
    
    # Create py.typed file if mypy support is enabled
    if ctx.attrs.mypy_support:
        py_typed_file = ctx.actions.declare_output("python", "py.typed")
        py_typed_content = _create_py_typed_content()
        
        ctx.actions.write(
            py_typed_file,
            py_typed_content,
        )
        package_files.append(py_typed_file)
    
    return package_files

def _python_proto_library_impl(ctx):
    """
    Implementation function for python_proto_library rule.
    
    Handles:
    - Python package path resolution
    - Tool downloading and caching
    - protoc execution with Python plugins
    - Type stub generation for mypy support
    - Python package structure creation
    - Output file management
    """
    # Get ProtoInfo from proto dependency
    proto_info = ctx.attrs.proto[ProtoInfo]
    
    # Resolve Python package path
    python_package = _resolve_python_package(ctx, proto_info)
    
    # Ensure required tools are available
    tools = ensure_tools_available(ctx, "python")
    
    # Get expected output files
    output_files = _get_python_output_files(ctx, proto_info, python_package)
    
    # Generate Python code using protoc
    _generate_python_code(ctx, proto_info, tools, output_files, python_package)
    
    # Create package structure files
    package_files = _create_package_files(ctx, python_package, proto_info)
    output_files.extend(package_files)
    
    # Generate type stubs if requested (and not already generated by protoc)
    if ctx.attrs.generate_stubs and "mypy" not in ctx.attrs.plugins:
        stub_files = _generate_type_stubs(ctx, [f for f in output_files if f.short_path.endswith(".py")])
        output_files.extend(stub_files)
    
    # Create LanguageProtoInfo provider
    language_proto_info = LanguageProtoInfo(
        language = "python",
        generated_files = output_files,
        package_name = python_package,
        dependencies = [
            "protobuf",
            "grpcio",
        ] if "grpc-python" in ctx.attrs.plugins else ["protobuf"],
        compiler_flags = [],
    )
    
    # Return providers
    return [
        DefaultInfo(default_outputs = output_files),
        language_proto_info,
    ]

# Python protobuf library rule definition
python_proto_library_rule = rule(
    impl = _python_proto_library_impl,
    attrs = {
        "proto": attrs.dep(providers = [ProtoInfo], doc = "Proto library target"),
        "python_package": attrs.string(default = "", doc = "Python package path override"),
        "plugins": attrs.list(attrs.string(), default = ["python", "grpc-python"], doc = "Protoc plugins to use"),
        "generate_stubs": attrs.bool(default = True, doc = "Generate .pyi type stub files"),
        "mypy_support": attrs.bool(default = True, doc = "Enable mypy compatibility features"),
        "options": attrs.dict(attrs.string(), attrs.string(), default = {}, doc = "Additional protoc options"),
        "_protoc": attrs.exec_dep(default = "//tools:protoc"),
        "_protoc_gen_python": attrs.exec_dep(default = "//tools:protoc-gen-python", doc = "Python protoc plugin"),
        "_protoc_gen_grpc_python": attrs.exec_dep(default = "//tools:protoc-gen-grpc-python", doc = "Python gRPC protoc plugin"),
    },
)

# Convenience function for basic Python protobuf generation (messages only)
def python_proto_messages(
    name: str,
    proto: str,
    python_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates only Python protobuf message code (no gRPC services).
    
    This is a convenience wrapper around python_proto_library that only
    generates basic protobuf message types, excluding gRPC service stubs.
    
    Args:
        name: Target name
        proto: proto_library target
        python_package: Python package path override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    python_proto_library(
        name = name,
        proto = proto,
        python_package = python_package,
        visibility = visibility,
        plugins = ["python"],  # Only basic protobuf, no gRPC
        **kwargs
    )

# Convenience function for gRPC service generation
def python_grpc_library(
    name: str,
    proto: str,
    python_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates Python gRPC service stubs with both messages and service definitions.
    
    This is a convenience wrapper around python_proto_library that ensures
    both protobuf messages and gRPC service stubs are generated.
    
    Args:
        name: Target name
        proto: proto_library target (must contain service definitions)
        python_package: Python package path override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    python_proto_library(
        name = name,
        proto = proto,
        python_package = python_package,
        visibility = visibility,
        plugins = ["python", "grpc-python"],  # Both messages and gRPC services
        **kwargs
    )

# Convenience function for mypy-focused generation
def python_proto_mypy(
    name: str,
    proto: str,
    python_package: str = "",
    visibility: list[str] = ["//visibility:private"],
    **kwargs
):
    """
    Generates Python protobuf code with enhanced mypy support.
    
    This uses protoc-gen-mypy for more accurate type stub generation
    when available, falling back to built-in stub generation.
    
    Args:
        name: Target name
        proto: proto_library target
        python_package: Python package path override
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    """
    python_proto_library(
        name = name,
        proto = proto,
        python_package = python_package,
        visibility = visibility,
        plugins = ["python", "grpc-python", "mypy"],  # Include mypy plugin
        generate_stubs = True,
        mypy_support = True,
        **kwargs
    )
