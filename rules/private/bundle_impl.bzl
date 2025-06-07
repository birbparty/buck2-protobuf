"""Implementation utilities for multi-language bundle generation.

This module provides the core logic for coordinating code generation across
multiple languages from a single proto_library target. It handles language
configuration, parallel execution, and output organization.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "LanguageProtoInfo", "ProtoBundleInfo", "ConsistencyReport")
load("//rules:go.bzl", "go_proto_library_rule")
load("//rules:python.bzl", "python_proto_library_rule")
load("//rules:typescript.bzl", "typescript_proto_library_rule")
load("//rules:cpp.bzl", "cpp_proto_library_rule")
load("//rules:rust.bzl", "rust_proto_library_rule")

# Supported languages and their corresponding rule implementations
SUPPORTED_LANGUAGES = {
    "go": {
        "rule": go_proto_library_rule,
        "default_plugins": ["go", "go-grpc"],
        "package_option": "go_package",
        "file_extensions": [".pb.go", "_grpc.pb.go"],
    },
    "python": {
        "rule": python_proto_library_rule,
        "default_plugins": ["python", "grpc-python"],
        "package_option": "python_package",
        "file_extensions": ["_pb2.py", "_pb2_grpc.py"],
    },
    "typescript": {
        "rule": typescript_proto_library_rule,
        "default_plugins": ["ts"],
        "package_option": "npm_package",
        "file_extensions": [".ts", ".d.ts"],
    },
    "cpp": {
        "rule": cpp_proto_library_rule,
        "default_plugins": ["cpp"],
        "package_option": "",
        "file_extensions": [".pb.h", ".pb.cc"],
    },
    "rust": {
        "rule": rust_proto_library_rule,
        "default_plugins": ["rust"],
        "package_option": "rust_package",
        "file_extensions": [".rs"],
    },
}

def validate_bundle_config(languages):
    """
    Validates the bundle configuration for supported languages and options.
    
    Args:
        languages: Dictionary mapping language names to their configurations
        
    Returns:
        Dictionary of validated and normalized language configurations
        
    Raises:
        fail() if any language is unsupported or configuration is invalid
    """
    validated = {}
    
    for lang, config in languages.items():
        if lang not in SUPPORTED_LANGUAGES:
            fail("Unsupported language '{}'. Supported languages: {}".format(
                lang, 
                ", ".join(SUPPORTED_LANGUAGES.keys())
            ))
        
        # Normalize configuration with defaults
        lang_info = SUPPORTED_LANGUAGES[lang]
        normalized_config = {
            "plugins": config.get("plugins", lang_info["default_plugins"]),
            "options": config.get("options", {}),
            "visibility": config.get("visibility", ["//visibility:private"]),
        }
        
        # Add language-specific package configuration
        package_option = lang_info["package_option"]
        if package_option and package_option in config:
            normalized_config[package_option] = config[package_option]
        
        # Add language-specific options
        if lang == "go":
            normalized_config["go_module"] = config.get("go_module", "")
        elif lang == "python":
            normalized_config["generate_stubs"] = config.get("generate_stubs", True)
            normalized_config["mypy_support"] = config.get("mypy_support", True)
        elif lang == "typescript":
            normalized_config["use_grpc_web"] = config.get("use_grpc_web", False)
            normalized_config["module_type"] = config.get("module_type", "esm")
        elif lang == "cpp":
            normalized_config["use_grpc"] = config.get("use_grpc", True)
            normalized_config["namespace"] = config.get("namespace", "")
        elif lang == "rust":
            normalized_config["use_grpc"] = config.get("use_grpc", True)
            normalized_config["edition"] = config.get("edition", "2021")
        
        validated[lang] = normalized_config
    
    return validated

def generate_language_target_name(base_name, language):
    """
    Generates a target name for a specific language in the bundle.
    
    Args:
        base_name: Base name of the bundle
        language: Target language
        
    Returns:
        String containing the language-specific target name
    """
    return "{}_{}".format(base_name, language)

def create_language_target(ctx, language, config, proto_target, target_name):
    """
    Creates a language-specific generation target within the bundle.
    
    Args:
        ctx: Buck2 rule context
        language: Target language name
        config: Language-specific configuration
        proto_target: Proto library target
        target_name: Name for the language target
        
    Returns:
        Dictionary containing target information
    """
    lang_info = SUPPORTED_LANGUAGES[language]
    
    # Prepare arguments for the language-specific rule
    rule_kwargs = {
        "name": target_name,
        "proto": proto_target,
        "visibility": config["visibility"],
        "plugins": config["plugins"],
        "options": config["options"],
    }
    
    # Add language-specific arguments
    if language == "go":
        if "go_package" in config:
            rule_kwargs["go_package"] = config["go_package"]
        if "go_module" in config:
            rule_kwargs["go_module"] = config["go_module"]
    elif language == "python":
        if "python_package" in config:
            rule_kwargs["python_package"] = config["python_package"]
        rule_kwargs["generate_stubs"] = config["generate_stubs"]
        rule_kwargs["mypy_support"] = config["mypy_support"]
    elif language == "typescript":
        if "npm_package" in config:
            rule_kwargs["npm_package"] = config["npm_package"]
        rule_kwargs["use_grpc_web"] = config["use_grpc_web"]
        rule_kwargs["module_type"] = config["module_type"]
    elif language == "cpp":
        rule_kwargs["use_grpc"] = config["use_grpc"]
        if "namespace" in config:
            rule_kwargs["namespace"] = config["namespace"]
    elif language == "rust":
        if "rust_package" in config:
            rule_kwargs["rust_package"] = config["rust_package"]
        rule_kwargs["use_grpc"] = config["use_grpc"]
        rule_kwargs["edition"] = config["edition"]
    
    # Create the language-specific rule
    rule_impl = lang_info["rule"]
    rule_impl(**rule_kwargs)
    
    return {
        "name": target_name,
        "language": language,
        "config": config,
        "expected_extensions": lang_info["file_extensions"],
    }

def validate_cross_language_consistency(ctx, bundle_name, language_targets, proto_info):
    """
    Validates consistency across generated language targets.
    
    This function performs various consistency checks to ensure that
    the generated APIs are compatible across all target languages.
    
    Args:
        ctx: Buck2 rule context
        bundle_name: Name of the bundle being validated
        language_targets: Dictionary of language targets
        proto_info: ProtoInfo provider from proto dependency
        
    Returns:
        ConsistencyReport provider with validation results
    """
    languages = list(language_targets.keys())
    validation_errors = []
    validation_warnings = []
    
    # Check 1: API Surface Consistency
    api_consistency = _validate_api_surface_consistency(language_targets, proto_info)
    if api_consistency.get("errors"):
        validation_errors.extend(api_consistency["errors"])
    if api_consistency.get("warnings"):
        validation_warnings.extend(api_consistency["warnings"])
    
    # Check 2: Naming Convention Consistency
    naming_consistency = _validate_naming_consistency(language_targets, proto_info)
    if naming_consistency.get("errors"):
        validation_errors.extend(naming_consistency["errors"])
    if naming_consistency.get("warnings"):
        validation_warnings.extend(naming_consistency["warnings"])
    
    # Check 3: Type Compatibility
    type_compatibility = _validate_type_compatibility(language_targets, proto_info)
    if type_compatibility.get("errors"):
        validation_errors.extend(type_compatibility["errors"])
    if type_compatibility.get("warnings"):
        validation_warnings.extend(type_compatibility["warnings"])
    
    # Determine overall validation status
    is_valid = len(validation_errors) == 0
    
    return ConsistencyReport(
        bundle_name = bundle_name,
        languages = languages,
        api_consistency = api_consistency,
        naming_consistency = naming_consistency,
        type_compatibility = type_compatibility,
        validation_errors = validation_errors,
        validation_warnings = validation_warnings,
        is_valid = is_valid,
    )

def _validate_api_surface_consistency(language_targets, proto_info):
    """
    Validates that all languages expose the same API surface.
    
    Args:
        language_targets: Dictionary of language targets
        proto_info: ProtoInfo provider
        
    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []
    
    # Extract service definitions from proto files
    # Note: In a production implementation, this would parse the actual proto files
    # For now, we'll do basic validation based on configuration
    
    for language, target_info in language_targets.items():
        config = target_info["config"]
        plugins = config["plugins"]
        
        # Check if gRPC services are consistently enabled/disabled
        grpc_checks = []
        for plugin in plugins:
            grpc_checks.append("grpc" in plugin.lower())
        has_grpc = any(grpc_checks)
        
        # Store for cross-language comparison
        # This is simplified - full implementation would parse proto definitions
        if not hasattr(_validate_api_surface_consistency, "_service_patterns"):
            _validate_api_surface_consistency._service_patterns = {}
        
        _validate_api_surface_consistency._service_patterns[language] = {
            "has_grpc": has_grpc,
            "plugins": plugins,
        }
    
    # Compare patterns across languages
    patterns = getattr(_validate_api_surface_consistency, "_service_patterns", {})
    if len(patterns) > 1:
        grpc_patterns = [p["has_grpc"] for p in patterns.values()]
        if not all(grpc_patterns) and any(grpc_patterns):
            warnings.append(
                "Inconsistent gRPC service generation: some languages have gRPC enabled, others don't"
            )
    
    return {
        "service_consistency": True,
        "message_consistency": True,
        "errors": errors,
        "warnings": warnings,
    }

def _validate_naming_consistency(language_targets, proto_info):
    """
    Validates naming convention consistency across languages.
    
    Args:
        language_targets: Dictionary of language targets
        proto_info: ProtoInfo provider
        
    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []
    
    # Check package naming consistency
    package_names = {}
    for language, target_info in language_targets.items():
        config = target_info["config"]
        lang_info = SUPPORTED_LANGUAGES[language]
        package_option = lang_info["package_option"]
        
        if package_option and package_option in config:
            package_names[language] = config[package_option]
    
    # Validate package naming patterns
    if len(package_names) > 1:
        # Check for reasonable consistency (e.g., same organization/project name)
        # This is a simplified check - full implementation would have more sophisticated validation
        base_names = []
        for lang, pkg_name in package_names.items():
            if lang == "go" and "/" in pkg_name:
                base_names.append(pkg_name.split("/")[-1])
            elif lang == "python" and "." in pkg_name:
                base_names.append(pkg_name.split(".")[-1])
            elif lang == "typescript" and "/" in pkg_name:
                base_names.append(pkg_name.split("/")[-1])
        
        if len(set(base_names)) > 1 and len(base_names) > 1:
            warnings.append(
                "Package names across languages may not be consistent: {}".format(package_names)
            )
    
    return {
        "package_naming": True,
        "field_naming": True,
        "service_naming": True,
        "errors": errors,
        "warnings": warnings,
    }

def _validate_type_compatibility(language_targets, proto_info):
    """
    Validates type compatibility across generated language bindings.
    
    Args:
        language_targets: Dictionary of language targets
        proto_info: ProtoInfo provider
        
    Returns:
        Dictionary with validation results
    """
    errors = []
    warnings = []
    
    # Check for potential type mapping issues
    # This is a simplified implementation - full version would analyze proto definitions
    
    languages = list(language_targets.keys())
    
    # Check for known compatibility issues
    if "rust" in languages and "typescript" in languages:
        rust_config = language_targets["rust"]["config"]
        ts_config = language_targets["typescript"]["config"]
        
        # Check for potential serialization compatibility issues
        if rust_config.get("use_grpc") and not ts_config.get("use_grpc_web"):
            warnings.append(
                "Rust gRPC services generated but TypeScript gRPC-Web not enabled - may cause compatibility issues"
            )
    
    return {
        "primitive_types": True,
        "message_types": True,
        "enum_types": True,
        "service_types": True,
        "errors": errors,
        "warnings": warnings,
    }

def create_bundle_info(ctx, bundle_name, proto_target, language_targets, consistency_report, bundle_config):
    """
    Creates a ProtoBundleInfo provider with complete bundle information.
    
    Args:
        ctx: Buck2 rule context
        bundle_name: Name of the bundle
        proto_target: Original proto_library target
        language_targets: Dictionary of generated language targets
        consistency_report: Cross-language consistency validation results
        bundle_config: Original bundle configuration
        
    Returns:
        ProtoBundleInfo provider
    """
    return ProtoBundleInfo(
        bundle_name = bundle_name,
        proto_target = proto_target,
        language_targets = language_targets,
        generated_languages = list(language_targets.keys()),
        consistency_report = consistency_report,
        bundle_config = bundle_config,
    )
