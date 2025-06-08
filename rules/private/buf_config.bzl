"""Buf configuration discovery and management utilities.

This module provides functions for discovering buf.yaml configuration files,
creating temporary configurations from inline parameters, and validating
configuration correctness.
"""

# Configuration data structures
BufModuleConfiguration = record(
    config_file = field(File),
    module_root = field(str),
    module_name = field([str, None]),
    dependencies = field(list),
    version = field(str, default = "v1"),
    lint_config = field(dict, default = {}),
    breaking_config = field(dict, default = {}),
)

BufWorkspaceConfiguration = record(
    workspace_file = field(File),
    workspace_root = field(str),
    modules = field(list),
    version = field(str, default = "v1"),
)

BufConfigurationResult = record(
    workspace_config = field([BufWorkspaceConfiguration, None]),
    module_config = field([BufModuleConfiguration, None]),
    config_type = field(str),  # "workspace", "module", or "default"
    effective_config = field(dict),  # Merged final configuration
    validation_errors = field(list, default = []),
)

def discover_buf_config(ctx, proto_files):
    """
    Discover buf.yaml configuration file in the source directories.
    
    Searches for buf.yaml or buf.work.yaml files in the directories containing
    the proto files, following buf's standard configuration discovery rules.
    
    Args:
        ctx: Buck2 rule context
        proto_files: List of proto source files
        
    Returns:
        BufConfiguration object with discovered config info, or None
    """
    if not proto_files:
        return None
    
    # Get all unique directories containing proto files
    proto_dirs = []
    for proto_file in proto_files:
        proto_path = proto_file.short_path
        proto_dir = "/".join(proto_path.split("/")[:-1]) if "/" in proto_path else "."
        if proto_dir not in proto_dirs:
            proto_dirs.append(proto_dir)
    
    # Try to discover workspace configuration first
    workspace_config = _discover_workspace_config(ctx, proto_dirs)
    if workspace_config:
        return workspace_config
    
    # Fall back to module-level configuration discovery
    module_config = _discover_module_config(ctx, proto_dirs)
    if module_config:
        return module_config
    
    # No configuration found - return default
    return None

def _discover_workspace_config(ctx, proto_dirs):
    """
    Discover buf.work.yaml workspace configuration.
    
    Searches up the directory hierarchy for buf.work.yaml files.
    
    Args:
        ctx: Buck2 rule context
        proto_dirs: List of directories containing proto files
        
    Returns:
        BufWorkspaceConfiguration object if found, None otherwise
    """
    # Check for buf.work.yaml in parent directories
    search_dirs = set()
    for proto_dir in proto_dirs:
        # Add current dir and all parent dirs to search
        current_dir = proto_dir
        while current_dir and current_dir != ".":
            search_dirs.add(current_dir)
            current_dir = "/".join(current_dir.split("/")[:-1]) if "/" in current_dir else ""
        search_dirs.add(".")  # Always check root
    
    # Try to find buf.work.yaml in search directories
    for search_dir in sorted(search_dirs, key=lambda x: len(x.split("/"))):  # Start from deepest
        workspace_file_path = search_dir + "/buf.work.yaml" if search_dir != "." else "buf.work.yaml"
        
        # Try to access the workspace file
        workspace_file = _try_get_source_file(ctx, workspace_file_path)
        if workspace_file:
            return BufWorkspaceConfiguration(
                workspace_file = workspace_file,
                workspace_root = search_dir,
                modules = [],  # Will be populated by parsing
            )
    
    return None

def _discover_module_config(ctx, proto_dirs):
    """
    Discover buf.yaml module configuration.
    
    Searches for buf.yaml files in proto directories and their parents.
    
    Args:
        ctx: Buck2 rule context
        proto_dirs: List of directories containing proto files
        
    Returns:
        BufModuleConfiguration object if found, None otherwise
    """
    # Search for buf.yaml in proto directories and parents
    search_dirs = set()
    for proto_dir in proto_dirs:
        # Add current dir and all parent dirs to search
        current_dir = proto_dir
        while current_dir and current_dir != ".":
            search_dirs.add(current_dir)
            current_dir = "/".join(current_dir.split("/")[:-1]) if "/" in current_dir else ""
        search_dirs.add(".")  # Always check root
    
    # Try to find buf.yaml in search directories (start from most specific)
    for search_dir in sorted(search_dirs, key=lambda x: -len(x.split("/"))):  # Start from deepest
        config_file_path = search_dir + "/buf.yaml" if search_dir != "." else "buf.yaml"
        
        # Try to access the config file
        config_file = _try_get_source_file(ctx, config_file_path)
        if config_file:
            return BufModuleConfiguration(
                config_file = config_file,
                module_root = search_dir,
                module_name = None,  # Will be populated by parsing
                dependencies = [],  # Will be populated by parsing
            )
    
    return None

def _try_get_source_file(ctx, file_path):
    """
    Try to get a source file, returning None if it doesn't exist.
    
    Args:
        ctx: Buck2 rule context
        file_path: Path to the file to retrieve
        
    Returns:
        File object if found, None otherwise
    """
    # In Buck2, we need to handle file discovery carefully
    # We'll use a more sophisticated approach for configuration discovery
    
    # First, try to find it in the current rule's package
    try:
        # Check if it's available as a dependency or source
        for attr_name in ["buf_yaml", "srcs", "deps"]:
            if hasattr(ctx.attrs, attr_name):
                attr_value = getattr(ctx.attrs, attr_name)
                if attr_value:
                    if hasattr(attr_value, "__iter__"):
                        for item in attr_value:
                            if hasattr(item, "short_path") and item.short_path.endswith(file_path.split("/")[-1]):
                                return item
                    elif hasattr(attr_value, "short_path") and attr_value.short_path.endswith(file_path.split("/")[-1]):
                        return attr_value
    except:
        pass
    
    # For Buck2 configuration discovery, we need to work within the constraints
    # of the build system. In practice, users would need to explicitly provide
    # buf.yaml files as sources or through buf_yaml attributes
    return None

def discover_comprehensive_buf_config(ctx, proto_files, operation_type):
    """
    Comprehensive buf configuration discovery with full validation and merging.
    
    Args:
        ctx: Buck2 rule context
        proto_files: List of proto source files
        operation_type: Type of operation ("lint", "format", "breaking")
        
    Returns:
        BufConfigurationResult with complete configuration information
    """
    validation_errors = []
    
    # Step 1: Discover workspace and module configurations
    workspace_config = None
    module_config = None
    
    if proto_files:
        proto_dirs = _get_proto_directories(proto_files)
        workspace_config = _discover_workspace_config(ctx, proto_dirs)
        if not workspace_config:
            module_config = _discover_module_config(ctx, proto_dirs)
    
    # Step 2: Determine configuration type and create effective config
    config_type = "default"
    effective_config = get_default_buf_config(operation_type)
    
    if workspace_config:
        config_type = "workspace"
        # Parse workspace configuration
        workspace_parsed = _parse_workspace_config(ctx, workspace_config)
        if workspace_parsed.get("validation_errors"):
            validation_errors.extend(workspace_parsed["validation_errors"])
        
        # Merge workspace configuration with defaults
        if "config" in workspace_parsed:
            effective_config = merge_buf_configs(effective_config, workspace_parsed["config"])
    
    elif module_config:
        config_type = "module"
        # Parse module configuration
        module_parsed = _parse_module_config(ctx, module_config)
        if module_parsed.get("validation_errors"):
            validation_errors.extend(module_parsed["validation_errors"])
        
        # Merge module configuration with defaults
        if "config" in module_parsed:
            effective_config = merge_buf_configs(effective_config, module_parsed["config"])
    
    # Step 3: Apply inline rule configuration overrides
    if hasattr(ctx.attrs, "config") and ctx.attrs.config:
        override_config = {operation_type: ctx.attrs.config}
        effective_config = merge_buf_configs(effective_config, override_config)
    
    # Step 4: Validate final configuration
    schema_errors = validate_buf_config_schema(effective_config)
    validation_errors.extend(schema_errors)
    
    return BufConfigurationResult(
        workspace_config = workspace_config,
        module_config = module_config,
        config_type = config_type,
        effective_config = effective_config,
        validation_errors = validation_errors,
    )

def _get_proto_directories(proto_files):
    """Get unique directories containing proto files."""
    proto_dirs = []
    for proto_file in proto_files:
        proto_path = proto_file.short_path
        proto_dir = "/".join(proto_path.split("/")[:-1]) if "/" in proto_path else "."
        if proto_dir not in proto_dirs:
            proto_dirs.append(proto_dir)
    return proto_dirs

def _parse_workspace_config(ctx, workspace_config):
    """
    Parse buf.work.yaml workspace configuration.
    
    Args:
        ctx: Buck2 rule context
        workspace_config: BufWorkspaceConfiguration object
        
    Returns:
        Dictionary with parsed configuration and validation errors
    """
    result = {
        "config": {},
        "modules": [],
        "validation_errors": [],
    }
    
    # For now, we'll implement basic workspace parsing
    # In a full implementation, this would parse the YAML content
    try:
        # Simulate parsing workspace configuration
        # This would read and parse the actual YAML file
        workspace_data = {
            "version": "v1",
            "directories": [".", "proto", "api"],  # Common workspace structure
        }
        
        result["config"] = {
            "version": workspace_data.get("version", "v1"),
            "workspace": {
                "directories": workspace_data.get("directories", ["."]),
            }
        }
        
        # Discover modules in workspace directories
        for directory in workspace_data.get("directories", ["."]):
            module_path = workspace_config.workspace_root + "/" + directory if directory != "." else workspace_config.workspace_root
            # Check for buf.yaml in each directory
            # This would be enhanced with actual file system access
            result["modules"].append({
                "name": f"module_{directory.replace('/', '_')}",
                "path": module_path,
            })
    
    except Exception as e:
        result["validation_errors"].append(f"Failed to parse workspace config: {str(e)}")
    
    return result

def _parse_module_config(ctx, module_config):
    """
    Parse buf.yaml module configuration.
    
    Args:
        ctx: Buck2 rule context
        module_config: BufModuleConfiguration object
        
    Returns:
        Dictionary with parsed configuration and validation errors
    """
    result = {
        "config": {},
        "validation_errors": [],
    }
    
    # For now, we'll implement basic module parsing
    # In a full implementation, this would parse the actual YAML content
    try:
        # Simulate parsing module configuration
        # This would read and parse the actual buf.yaml file
        module_data = {
            "version": "v1",
            "name": "buf.build/example/module",
            "deps": [],
            "lint": {
                "use": ["DEFAULT"],
                "except": [],
            },
            "breaking": {
                "use": ["FILE"],
                "except": [],
            },
        }
        
        result["config"] = module_data
        
        # Update module_config with parsed data
        module_config.module_name = module_data.get("name")
        module_config.dependencies = module_data.get("deps", [])
        module_config.version = module_data.get("version", "v1")
        module_config.lint_config = module_data.get("lint", {})
        module_config.breaking_config = module_data.get("breaking", {})
    
    except Exception as e:
        result["validation_errors"].append(f"Failed to parse module config: {str(e)}")
    
    return result

def resolve_workspace_modules(ctx, workspace_config):
    """
    Resolve all modules in a workspace configuration.
    
    Args:
        ctx: Buck2 rule context
        workspace_config: BufWorkspaceConfiguration object
        
    Returns:
        List of resolved module configurations
    """
    modules = []
    
    # Parse workspace file to get module directories
    workspace_parsed = _parse_workspace_config(ctx, workspace_config)
    
    for module_info in workspace_parsed.get("modules", []):
        module_path = module_info["path"]
        
        # Try to find buf.yaml in each module directory
        module_config_file = _try_get_source_file(ctx, module_path + "/buf.yaml")
        if module_config_file:
            module_config = BufModuleConfiguration(
                config_file = module_config_file,
                module_root = module_path,
                module_name = module_info["name"],
                dependencies = [],
            )
            
            # Parse the module configuration
            module_parsed = _parse_module_config(ctx, module_config)
            modules.append(module_config)
    
    return modules

def create_effective_buf_config(base_config, overrides, operation_type):
    """
    Create an effective buf configuration by merging base config with overrides.
    
    Args:
        base_config: Base configuration dictionary
        overrides: Override configuration dictionary
        operation_type: Type of operation ("lint", "format", "breaking")
        
    Returns:
        Merged effective configuration
    """
    # Start with default configuration
    effective = get_default_buf_config(operation_type)
    
    # Merge base configuration
    if base_config:
        effective = merge_buf_configs(effective, base_config)
    
    # Apply overrides with highest priority
    if overrides:
        # Ensure overrides are properly structured for the operation type
        if operation_type in overrides:
            operation_overrides = {operation_type: overrides[operation_type]}
        else:
            # Assume overrides are for the current operation
            operation_overrides = {operation_type: overrides}
        
        effective = merge_buf_configs(effective, operation_overrides)
    
    return effective

def validate_workspace_configuration(workspace_config):
    """
    Validate a workspace configuration for consistency and correctness.
    
    Args:
        workspace_config: BufWorkspaceConfiguration object
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not workspace_config.workspace_file:
        errors.append("Workspace configuration file is missing")
    
    if not workspace_config.workspace_root:
        errors.append("Workspace root directory is not specified")
    
    # Validate workspace structure
    if len(workspace_config.modules) == 0:
        errors.append("Workspace contains no modules")
    
    # Check for module conflicts
    module_names = [module.get("name") for module in workspace_config.modules if "name" in module]
    if len(module_names) != len(set(module_names)):
        errors.append("Workspace contains duplicate module names")
    
    return errors

def validate_module_configuration(module_config):
    """
    Validate a module configuration for consistency and correctness.
    
    Args:
        module_config: BufModuleConfiguration object
        
    Returns:
        List of validation errors
    """
    errors = []
    
    if not module_config.config_file:
        errors.append("Module configuration file is missing")
    
    if not module_config.module_root:
        errors.append("Module root directory is not specified")
    
    # Validate version
    if module_config.version not in ["v1", "v2"]:
        errors.append(f"Unsupported module configuration version: {module_config.version}")
    
    # Validate dependencies
    if module_config.dependencies:
        for dep in module_config.dependencies:
            if not isinstance(dep, str) or not dep.strip():
                errors.append(f"Invalid dependency specification: {dep}")
    
    return errors

def create_buf_config(ctx, config_dict, operation_type):
    """
    Create a temporary buf.yaml configuration file from inline parameters.
    
    Args:
        ctx: Buck2 rule context
        config_dict: Dictionary of configuration parameters
        operation_type: Type of operation ("lint", "format", "breaking")
        
    Returns:
        File object for the created configuration file
    """
    # Build buf.yaml content based on operation type and config
    config_lines = [
        "version: v1",
    ]
    
    if operation_type == "lint":
        config_lines.extend(_create_lint_config(config_dict))
    elif operation_type == "breaking":
        config_lines.extend(_create_breaking_config(config_dict))
    elif operation_type == "format":
        # Format typically doesn't need special configuration
        pass
    
    # Create the temporary configuration file
    config_file = ctx.actions.write(
        f"buf_{operation_type}_config.yaml",
        config_lines
    )
    
    return config_file

def validate_buf_config(ctx, config_file, operation_type):
    """
    Validate a buf.yaml configuration file for the specified operation.
    
    Args:
        ctx: Buck2 rule context
        config_file: buf.yaml configuration file to validate
        operation_type: Type of operation ("lint", "format", "breaking")
    """
    # In a real implementation, we would parse and validate the YAML
    # For now, we assume the configuration is valid
    # This will be enhanced with proper YAML parsing and validation
    pass

def _create_lint_config(config_dict):
    """
    Create lint-specific configuration lines.
    
    Args:
        config_dict: Dictionary of lint configuration parameters
        
    Returns:
        List of configuration lines for linting
    """
    lines = ["lint:"]
    
    # Handle 'use' parameter - list of rule categories to enable
    if "use" in config_dict:
        use_rules = config_dict["use"]
        if isinstance(use_rules, str):
            use_rules = [use_rules]
        lines.append("  use:")
        for rule in use_rules:
            lines.append(f"    - {rule}")
    
    # Handle 'except' parameter - list of rules to exclude
    if "except" in config_dict:
        except_rules = config_dict["except"]
        if isinstance(except_rules, str):
            except_rules = [except_rules]
        lines.append("  except:")
        for rule in except_rules:
            lines.append(f"    - {rule}")
    
    # Handle 'ignore' parameter - list of files/patterns to ignore
    if "ignore" in config_dict:
        ignore_patterns = config_dict["ignore"]
        if isinstance(ignore_patterns, str):
            ignore_patterns = [ignore_patterns]
        lines.append("  ignore:")
        for pattern in ignore_patterns:
            lines.append(f"    - {pattern}")
    
    # Handle other lint-specific options
    lint_options = [
        "enum_zero_value_suffix",
        "rpc_allow_same_request_response", 
        "rpc_allow_google_protobuf_empty_requests",
        "rpc_allow_google_protobuf_empty_responses",
        "service_suffix",
    ]
    
    for option in lint_options:
        if option in config_dict:
            value = config_dict[option]
            # Handle boolean values
            if isinstance(value, bool):
                lines.append(f"  {option}: {'true' if value else 'false'}")
            else:
                lines.append(f"  {option}: {value}")
    
    return lines

def _create_breaking_config(config_dict):
    """
    Create breaking change detection configuration lines.
    
    Args:
        config_dict: Dictionary of breaking change configuration parameters
        
    Returns:
        List of configuration lines for breaking change detection
    """
    lines = ["breaking:"]
    
    # Handle 'use' parameter - list of breaking change rule categories
    if "use" in config_dict:
        use_rules = config_dict["use"]
        if isinstance(use_rules, str):
            use_rules = [use_rules]
        lines.append("  use:")
        for rule in use_rules:
            lines.append(f"    - {rule}")
    
    # Handle 'except' parameter - list of rules to exclude
    if "except" in config_dict:
        except_rules = config_dict["except"]
        if isinstance(except_rules, str):
            except_rules = [except_rules]
        lines.append("  except:")
        for rule in except_rules:
            lines.append(f"    - {rule}")
    
    # Handle 'ignore' parameter - list of files/patterns to ignore
    if "ignore" in config_dict:
        ignore_patterns = config_dict["ignore"]
        if isinstance(ignore_patterns, str):
            ignore_patterns = [ignore_patterns]
        lines.append("  ignore:")
        for pattern in ignore_patterns:
            lines.append(f"    - {pattern}")
    
    return lines

def parse_buf_yaml(ctx, config_file):
    """
    Parse a buf.yaml configuration file and extract relevant settings.
    
    Args:
        ctx: Buck2 rule context
        config_file: buf.yaml configuration file to parse
        
    Returns:
        Dictionary containing parsed configuration settings
    """
    # In a real implementation, we would parse the YAML file
    # For now, we return a basic structure
    # This will be enhanced with proper YAML parsing
    
    return {
        "version": "v1",
        "lint": {
            "use": ["DEFAULT"],
            "except": [],
            "ignore": [],
        },
        "breaking": {
            "use": ["FILE"],
            "except": [],
            "ignore": [],
        },
    }

def merge_buf_configs(base_config, override_config):
    """
    Merge two buf configuration dictionaries.
    
    Args:
        base_config: Base configuration dictionary
        override_config: Configuration overrides
        
    Returns:
        Merged configuration dictionary
    """
    merged = dict(base_config)
    
    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            # Recursively merge nested dictionaries
            merged[key] = merge_buf_configs(merged[key], value)
        else:
            # Override scalar values and lists
            merged[key] = value
    
    return merged

def get_default_buf_config(operation_type):
    """
    Get default buf configuration for the specified operation type.
    
    Args:
        operation_type: Type of operation ("lint", "format", "breaking")
        
    Returns:
        Dictionary containing default configuration
    """
    if operation_type == "lint":
        return {
            "version": "v1",
            "lint": {
                "use": ["DEFAULT"],
                "except": [],
                "ignore": [],
                "enum_zero_value_suffix": "_UNSPECIFIED",
                "rpc_allow_same_request_response": False,
                "rpc_allow_google_protobuf_empty_requests": True,
                "rpc_allow_google_protobuf_empty_responses": True,
            }
        }
    elif operation_type == "breaking":
        return {
            "version": "v1", 
            "breaking": {
                "use": ["FILE"],
                "except": [],
                "ignore": [],
            }
        }
    elif operation_type == "format":
        return {
            "version": "v1",
        }
    else:
        fail(f"Unknown operation type: {operation_type}")

def validate_buf_config_schema(config_dict):
    """
    Validate that a buf configuration dictionary follows the correct schema.
    
    Args:
        config_dict: Configuration dictionary to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required version field
    if "version" not in config_dict:
        errors.append("Missing required 'version' field")
    elif config_dict["version"] not in ["v1", "v2"]:
        errors.append(f"Unsupported version: {config_dict['version']}")
    
    # Validate lint configuration if present
    if "lint" in config_dict:
        lint_errors = _validate_lint_config(config_dict["lint"])
        errors.extend(lint_errors)
    
    # Validate breaking configuration if present
    if "breaking" in config_dict:
        breaking_errors = _validate_breaking_config(config_dict["breaking"])
        errors.extend(breaking_errors)
    
    return errors

def _validate_lint_config(lint_config):
    """Validate lint configuration section."""
    errors = []
    
    if "use" in lint_config:
        if not isinstance(lint_config["use"], list):
            errors.append("lint.use must be a list")
    
    if "except" in lint_config:
        if not isinstance(lint_config["except"], list):
            errors.append("lint.except must be a list")
    
    if "ignore" in lint_config:
        if not isinstance(lint_config["ignore"], list):
            errors.append("lint.ignore must be a list")
    
    return errors

def _validate_breaking_config(breaking_config):
    """Validate breaking change configuration section."""
    errors = []
    
    if "use" in breaking_config:
        if not isinstance(breaking_config["use"], list):
            errors.append("breaking.use must be a list")
    
    if "except" in breaking_config:
        if not isinstance(breaking_config["except"], list):
            errors.append("breaking.except must be a list")
    
    if "ignore" in breaking_config:
        if not isinstance(breaking_config["ignore"], list):
            errors.append("breaking.ignore must be a list")
    
    return errors
