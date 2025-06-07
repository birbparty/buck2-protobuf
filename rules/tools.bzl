"""Tool management utilities for protobuf Buck2 integration.

This module provides functionality for downloading, caching, and managing
protoc and protoc plugins. It integrates with the Python download scripts
and Buck2's action system for hermetic builds.
"""

load("//tools/platforms:common.bzl", "get_platform_info", "get_protoc_info", "get_plugin_info", "get_default_versions")


def get_target_platform(ctx = None):
    """
    Returns the current target platform for tool selection.
    
    Args:
        ctx: Buck2 rule context (optional)
    
    Returns:
        Platform string in format: "{os}-{arch}"
        Examples: "linux-x86_64", "darwin-arm64", "windows-x86_64"
    """
    # Use platform detection from common.bzl
    platform_info = get_platform_info()
    return platform_info["platform_string"]


def get_protoc_binary(ctx, version: str = "", platform: str = ""):
    """
    Downloads and caches the protoc binary for the specified version and platform.
    
    Args:
        ctx: Buck2 rule context
        version: Protoc version (e.g., "24.4"). Uses default if empty.
        platform: Target platform (e.g., "linux-x86_64"). Auto-detected if empty.
    
    Returns:
        File object pointing to the cached protoc binary
    """
    # Use default version if not specified
    if not version:
        default_versions = get_default_versions()
        version = default_versions["protoc"]
    
    # Use current platform if not specified
    if not platform:
        platform = get_target_platform(ctx)
    
    # Get protoc configuration
    protoc_info = get_protoc_info()
    if version not in protoc_info:
        fail("Unsupported protoc version: {}. Available versions: {}".format(
            version, protoc_info.keys()))
    
    if platform not in protoc_info[version]:
        fail("Unsupported platform for protoc {}: {}. Available platforms: {}".format(
            version, platform, protoc_info[version].keys()))
    
    config = protoc_info[version][platform]
    expected_checksum = config["sha256"]
    
    # Create cache directory name
    cache_key = "protoc-{}-{}".format(version, platform)
    
    # Create the download action
    download_script = ctx.attrs._download_protoc_script[DefaultInfo].default_outputs[0]
    output_file = ctx.actions.declare_output("tools", cache_key, config["binary_path"])
    
    # Create cache directory for the action
    cache_dir = ctx.actions.declare_output("tools", "cache")
    
    cmd = cmd_args([
        "python3",
        download_script,
        "--version", version,
        "--platform", platform,
        "--cache-dir", cache_dir.as_output(),
        "--checksum", expected_checksum,
    ])
    
    # Run the download script
    ctx.actions.run(
        cmd,
        category = "protoc_download",
        identifier = cache_key,
        inputs = [download_script],
        outputs = [output_file, cache_dir],
        env = {
            "PYTHONPATH": ".",
        },
        local_only = True,  # Downloads should run locally
    )
    
    return output_file


def get_plugin_binary(ctx, plugin: str, version: str = "", platform: str = ""):
    """
    Downloads and caches a protoc plugin binary.
    
    Args:
        ctx: Buck2 rule context
        plugin: Plugin name (e.g., "protoc-gen-go")
        version: Plugin version. Uses default if empty.
        platform: Target platform. Auto-detected if empty.
    
    Returns:
        File object pointing to the cached plugin binary
    """
    # Use default version if not specified
    if not version:
        default_versions = get_default_versions()
        if plugin in default_versions:
            version = default_versions[plugin]
        else:
            fail("No default version available for plugin: {}".format(plugin))
    
    # Use current platform if not specified
    if not platform:
        platform = get_target_platform(ctx)
    
    # Get plugin configuration
    plugin_info = get_plugin_info()
    if plugin not in plugin_info:
        fail("Unsupported plugin: {}. Available plugins: {}".format(
            plugin, plugin_info.keys()))
    
    if version not in plugin_info[plugin]:
        fail("Unsupported version for {}: {}. Available versions: {}".format(
            plugin, version, plugin_info[plugin].keys()))
    
    if platform not in plugin_info[plugin][version]:
        fail("Unsupported platform for {} {}: {}. Available platforms: {}".format(
            plugin, version, platform, plugin_info[plugin][version].keys()))
    
    config = plugin_info[plugin][version][platform]
    
    # Create cache directory name
    cache_key = "{}-{}-{}".format(plugin, version, platform)
    
    # Create the download action
    download_script = ctx.attrs._download_plugins_script[DefaultInfo].default_outputs[0]
    output_file = ctx.actions.declare_output("tools", cache_key, config["binary_path"])
    
    # Create cache directory for the action
    cache_dir = ctx.actions.declare_output("tools", "cache")
    
    cmd = cmd_args([
        "python3",
        download_script,
        "--plugin", plugin,
        "--version", version,
        "--platform", platform,
        "--cache-dir", cache_dir.as_output(),
    ])
    
    # Add checksum validation for binary plugins
    if "sha256" in config:
        cmd.add("--checksum", config["sha256"])
    
    # Run the download script
    ctx.actions.run(
        cmd,
        category = "plugin_download",
        identifier = cache_key,
        inputs = [download_script],
        outputs = [output_file, cache_dir],
        env = {
            "PYTHONPATH": ".",
        },
        local_only = True,  # Downloads should run locally
    )
    
    return output_file


def validate_tool_checksum(ctx, file, expected_checksum: str, tool_type: str = "protoc"):
    """
    Validates that a downloaded tool matches its expected SHA256 checksum.
    
    Args:
        ctx: Buck2 rule context
        file: Downloaded tool file
        expected_checksum: Expected SHA256 hash
        tool_type: Type of tool ("protoc" or "plugin")
    
    Returns:
        File object for the validated tool
    """
    validation_script = ctx.attrs._validate_tools_script[DefaultInfo].default_outputs[0]
    validated_output = ctx.actions.declare_output("validated", file.basename)
    
    cmd = cmd_args([
        "python3",
        validation_script,
        "--tool-path", file,
        "--tool-type", tool_type,
        "--expected-checksum", expected_checksum,
        "--verbose",
    ])
    
    # Run validation
    ctx.actions.run(
        cmd,
        category = "tool_validation",
        identifier = "{}_{}".format(tool_type, file.basename),
        inputs = [validation_script, file],
        outputs = [validated_output],
        env = {
            "PYTHONPATH": ".",
        },
    )
    
    return validated_output


def create_tool_cache_action(ctx, tools: dict):
    """
    Creates a Buck2 action that ensures all required tools are downloaded and cached.
    
    Args:
        ctx: Buck2 rule context
        tools: Dictionary mapping tool names to version requirements
    
    Returns:
        List of tool file objects
    """
    tool_files = []
    platform = get_target_platform(ctx)
    
    for tool_name, tool_version in tools.items():
        if tool_name == "protoc":
            tool_file = get_protoc_binary(ctx, tool_version, platform)
        else:
            tool_file = get_plugin_binary(ctx, tool_name, tool_version, platform)
        
        tool_files.append(tool_file)
    
    return tool_files


def get_protoc_command(ctx, protoc_binary, proto_files: list, output_dir, import_paths: list = [], plugins: dict = {}):
    """
    Creates a protoc command with proper arguments for Buck2 execution.
    
    Args:
        ctx: Buck2 rule context
        protoc_binary: Protoc binary file object
        proto_files: List of proto file objects to compile
        output_dir: Output directory for generated files
        import_paths: List of import paths for proto resolution
        plugins: Dictionary mapping plugin names to plugin binary file objects
    
    Returns:
        cmd_args object for protoc execution
    """
    cmd = cmd_args([protoc_binary])
    
    # Add import paths
    for import_path in import_paths:
        cmd.add("--proto_path={}".format(import_path))
    
    # Add plugin configurations
    for plugin_name, plugin_binary in plugins.items():
        cmd.add("--plugin={}={}".format(plugin_name, plugin_binary))
    
    # Add output directory
    cmd.add("--descriptor_set_out={}".format(output_dir))
    cmd.add("--include_imports")
    cmd.add("--include_source_info")
    
    # Add proto files
    cmd.add(proto_files)
    
    return cmd


def create_protoc_action(ctx, name: str, protoc_binary, proto_files: list, output_files: list, **kwargs):
    """
    Creates a Buck2 action that runs protoc to compile proto files.
    
    Args:
        ctx: Buck2 rule context
        name: Name/identifier for the action
        protoc_binary: Protoc binary file object
        proto_files: List of proto file objects to compile
        output_files: List of expected output file objects
        **kwargs: Additional arguments for protoc command generation
    
    Returns:
        None (action is registered with Buck2)
    """
    # Create output directory
    output_dir = ctx.actions.declare_output("gen")
    
    # Generate protoc command
    import_paths = kwargs.get("import_paths", [])
    plugins = kwargs.get("plugins", {})
    
    cmd = get_protoc_command(
        ctx, 
        protoc_binary, 
        proto_files, 
        output_dir.as_output(),
        import_paths,
        plugins
    )
    
    # Collect all inputs
    inputs = [protoc_binary] + proto_files
    inputs.extend(plugins.values())
    
    # Run protoc
    ctx.actions.run(
        cmd,
        category = "protoc",
        identifier = name,
        inputs = inputs,
        outputs = output_files + [output_dir],
        env = {
            "PATH": "/usr/bin:/bin",  # Basic PATH for protoc execution
        },
    )


# Rule attributes for tool management
TOOL_ATTRS = {
    "_download_protoc_script": attrs.source(
        default = "//tools:download_protoc.py",
        doc = "Python script for downloading protoc binaries",
    ),
    "_download_plugins_script": attrs.source(
        default = "//tools:download_plugins.py", 
        doc = "Python script for downloading protoc plugins",
    ),
    "_validate_tools_script": attrs.source(
        default = "//tools:validate_tools.py",
        doc = "Python script for validating tool integrity",
    ),
}


def get_tool_requirements(language: str):
    """
    Returns the tool requirements for a specific language.
    
    Args:
        language: Programming language (e.g., "go", "python", "cpp")
    
    Returns:
        Dictionary mapping tool names to required versions
    """
    base_tools = {
        "protoc": "",  # Use default version
    }
    
    language_tools = {
        "go": {
            "protoc-gen-go": "",
            "protoc-gen-go-grpc": "",
        },
        "python": {
            "protoc-gen-grpc-python": "",
        },
        "cpp": {
            # C++ support is built into protoc
        },
        "java": {
            # Java support is built into protoc
        },
        "javascript": {
            # Will be added in future tasks
        },
        "typescript": {
            # Will be added in future tasks
        },
        "rust": {
            # Will be added in future tasks
        },
    }
    
    tools = dict(base_tools)
    if language in language_tools:
        tools.update(language_tools[language])
    
    return tools


def ensure_tools_available(ctx, language: str):
    """
    Ensures all required tools for a language are downloaded and available.
    
    Args:
        ctx: Buck2 rule context
        language: Programming language
    
    Returns:
        Dictionary mapping tool names to file objects
    """
    requirements = get_tool_requirements(language)
    tools = {}
    
    for tool_name, version in requirements.items():
        if tool_name == "protoc":
            tools[tool_name] = get_protoc_binary(ctx, version)
        else:
            tools[tool_name] = get_plugin_binary(ctx, tool_name, version)
    
    return tools
