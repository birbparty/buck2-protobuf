"""Utility functions for protobuf Buck2 integration.

This module provides common utility functions used across the protobuf rules.
"""

def merge_proto_infos(proto_infos):
    """
    Merges multiple ProtoInfo providers into a single transitive set.
    
    Args:
        proto_infos: List of ProtoInfo providers to merge
    
    Returns:
        Dictionary with merged transitive collections
    """
    if not proto_infos:
        return {
            "transitive_descriptor_sets": [],
            "transitive_proto_files": [],
            "transitive_import_paths": [],
        }
    
    transitive_descriptor_sets = []
    transitive_proto_files = []
    transitive_import_paths = []
    
    for proto_info in proto_infos:
        # Add the current proto info's files
        if hasattr(proto_info, 'descriptor_set') and proto_info.descriptor_set:
            transitive_descriptor_sets.append(proto_info.descriptor_set)
        if hasattr(proto_info, 'proto_files'):
            transitive_proto_files.extend(proto_info.proto_files)
        if hasattr(proto_info, 'import_paths'):
            transitive_import_paths.extend(proto_info.import_paths)
            
        # Add transitive dependencies
        if hasattr(proto_info, 'transitive_descriptor_sets'):
            transitive_descriptor_sets.extend(proto_info.transitive_descriptor_sets)
        if hasattr(proto_info, 'transitive_proto_files'):
            transitive_proto_files.extend(proto_info.transitive_proto_files)
        if hasattr(proto_info, 'transitive_import_paths'):
            transitive_import_paths.extend(proto_info.transitive_import_paths)
    
    # Deduplicate while preserving order
    return {
        "transitive_descriptor_sets": _dedupe_list(transitive_descriptor_sets),
        "transitive_proto_files": _dedupe_list(transitive_proto_files),
        "transitive_import_paths": _dedupe_list(transitive_import_paths),
    }

def get_proto_import_path(src, import_prefix = "", strip_import_prefix = ""):
    """
    Computes the import path for a proto file based on prefixes.
    
    Args:
        src: Source proto file
        import_prefix: Prefix to add to import paths
        strip_import_prefix: Prefix to strip from import paths
    
    Returns:
        Computed import path string
    """
    # Get the base path
    if hasattr(src, 'short_path'):
        path = src.short_path
    else:
        path = str(src)
    
    # Strip prefix if specified
    if strip_import_prefix and path.startswith(strip_import_prefix):
        # Remove the prefix and any leading slash
        path = path[len(strip_import_prefix):]
        if path.startswith("/"):
            path = path[1:]
    
    # Add prefix if specified
    if import_prefix:
        # Ensure prefix ends with slash if not empty
        prefix = import_prefix
        if not prefix.endswith("/"):
            prefix += "/"
        path = prefix + path
    
    return path

def get_proto_package_option(proto_content, option_name):
    """
    Extracts a package option from proto file content.
    
    Note: This is a simplified implementation for Task 002.
    In a production system, we would use a proper proto parser.
    
    Args:
        proto_content: Content of the proto file as string
        option_name: Name of the option to extract (e.g., "go_package")
    
    Returns:
        Option value if found, empty string otherwise
    """
    # Simple string-based search for option declarations
    # Look for: option go_package = "value";
    lines = proto_content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('option ' + option_name + ' ='):
            # Extract the quoted value
            parts = line.split('"')
            if len(parts) >= 2:
                return parts[1]
    return ""

def validate_proto_library_inputs(ctx):
    """
    Validates inputs to proto_library rule.
    
    Args:
        ctx: Rule context
        
    Raises:
        fail() with descriptive error message if validation fails
    """
    # Check that srcs is not empty
    if not ctx.attrs.srcs:
        fail("proto_library '{}' requires at least one .proto file in srcs".format(ctx.label))
    
    # Check that all srcs are .proto files
    for src in ctx.attrs.srcs:
        if not src.short_path.endswith(".proto"):
            fail("proto_library '{}' src '{}' must be a .proto file".format(
                ctx.label, src.short_path))
    
    # Check import prefix/strip prefix validity
    if ctx.attrs.strip_import_prefix and ctx.attrs.import_prefix:
        if ctx.attrs.strip_import_prefix.startswith(ctx.attrs.import_prefix):
            fail("proto_library '{}': strip_import_prefix '{}' cannot start with import_prefix '{}'".format(
                ctx.label, ctx.attrs.strip_import_prefix, ctx.attrs.import_prefix))

def create_descriptor_set_action(ctx, proto_files, deps_descriptor_sets, import_paths):
    """
    Creates a Buck2 action to compile proto files to a descriptor set.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files to compile
        deps_descriptor_sets: List of dependency descriptor sets
        import_paths: List of import paths for resolution
    
    Returns:
        Generated descriptor set file
    """
    # Create output descriptor set file
    descriptor_set = ctx.actions.declare_output("{}.descriptorset".format(ctx.label.name))
    
    # For Task 002, create a stub descriptor set file to test rule structure
    # This will be replaced with actual protoc execution in Task 003
    stub_content = "# Stub descriptor set for proto files: {}\n".format(
        ", ".join([f.short_path for f in proto_files])
    )
    stub_content += "# Import paths: {}\n".format(", ".join(import_paths))
    stub_content += "# Dependencies: {}\n".format(len(deps_descriptor_sets))
    
    ctx.actions.write(
        descriptor_set,
        stub_content,
    )
    
    return descriptor_set

def _dedupe_list(items):
    """
    Deduplicates a list while preserving order.
    
    Args:
        items: List to deduplicate
        
    Returns:
        Deduplicated list
    """
    seen = {}
    result = []
    for item in items:
        if item not in seen:
            seen[item] = True
            result.append(item)
    return result
