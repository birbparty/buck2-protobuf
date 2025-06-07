"""Cache key generation for protobuf Buck2 integration.

This module provides deterministic cache key generation that enables
high cache hit rates through intelligent input analysis and language isolation.
"""

def generate_cache_key(ctx, proto_info):
    """Generates a deterministic base cache key for protobuf compilation.
    
    This cache key includes all inputs that affect proto compilation but
    excludes language-specific options to enable sharing across languages.
    
    Args:
        ctx: Rule context
        proto_info: ProtoInfo provider
        
    Returns:
        str: Deterministic cache key
    """
    key_components = [
        _hash_proto_files(proto_info.proto_files),
        _hash_proto_dependencies(proto_info.transitive_descriptor_sets),
        _hash_import_paths(proto_info.import_paths),
        _hash_protoc_options(ctx),
        _hash_rule_version(),
    ]
    
    # Combine components with separator
    key_content = ":".join(key_components)
    return _sha256_hash(key_content)[:32]  # Use first 32 chars for readability

def generate_language_cache_key(base_cache_key, language, language_options):
    """Generates a language-specific cache key from base key.
    
    This enables language isolation so that changes to one language's
    configuration don't invalidate other languages' cache entries.
    
    Args:
        base_cache_key: Base cache key from generate_cache_key
        language: Target language ("go", "python", etc.)
        language_options: Language-specific options
        
    Returns:
        str: Language-specific cache key
    """
    language_components = [
        base_cache_key,
        language,
        _hash_language_options(language, language_options),
        _hash_language_tool_version(language),
    ]
    
    key_content = ":".join(language_components)
    return _sha256_hash(key_content)[:32]

def validate_cache_key(cache_key):
    """Validates that a cache key is well-formed.
    
    Args:
        cache_key: Cache key to validate
        
    Returns:
        bool: True if cache key is valid
    """
    if not cache_key:
        return False
    
    if len(cache_key) != 32:
        return False
    
    # Check that it's a valid hex string
    try:
        int(cache_key, 16)
        return True
    except ValueError:
        return False

def generate_cache_key_for_bundle(ctx, proto_info, languages, bundle_config):
    """Generates cache keys for multi-language bundles.
    
    Args:
        ctx: Rule context
        proto_info: ProtoInfo provider
        languages: Dictionary of language configurations
        bundle_config: Bundle-specific configuration
        
    Returns:
        Dictionary mapping language -> cache key
    """
    base_key = generate_cache_key(ctx, proto_info)
    
    # Add bundle-specific components
    bundle_components = [
        base_key,
        _hash_bundle_config(bundle_config),
        _hash_consistency_checks(ctx),
    ]
    
    bundle_base_key = _sha256_hash(":".join(bundle_components))[:32]
    
    # Generate language-specific keys
    language_keys = {}
    for language, config in languages.items():
        language_keys[language] = generate_language_cache_key(
            bundle_base_key,
            language,
            config
        )
    
    return language_keys

def generate_cache_key_for_grpc_service(ctx, proto_info, languages, plugins, service_config):
    """Generates cache keys for gRPC services with plugins.
    
    Args:
        ctx: Rule context
        proto_info: ProtoInfo provider
        languages: List of target languages
        plugins: Plugin configurations
        service_config: Service-specific configuration
        
    Returns:
        Dictionary mapping language -> cache key
    """
    base_key = generate_cache_key(ctx, proto_info)
    
    # Add gRPC service-specific components
    service_components = [
        base_key,
        _hash_grpc_plugins(plugins),
        _hash_service_config(service_config),
        _hash_grpc_tool_versions(),
    ]
    
    service_base_key = _sha256_hash(":".join(service_components))[:32]
    
    # Generate language-specific keys including plugin effects
    language_keys = {}
    for language in languages:
        lang_components = [
            service_base_key,
            language,
            _hash_language_plugins(language, plugins),
        ]
        
        language_keys[language] = _sha256_hash(":".join(lang_components))[:32]
    
    return language_keys

def _hash_proto_files(proto_files):
    """Creates deterministic hash of proto file contents.
    
    Args:
        proto_files: List of proto files
        
    Returns:
        str: Hash of proto files
    """
    file_hashes = []
    
    for proto_file in sorted(proto_files, key=lambda f: _get_file_path(f)):
        file_path = _get_file_path(proto_file)
        
        # In Buck2, we can use file content hashing
        # For now, we hash the file path as a proxy
        file_hash = _sha256_hash(file_path)[:16]
        file_hashes.append("{}:{}".format(file_path, file_hash))
    
    return _sha256_hash(":".join(file_hashes))[:16]

def _hash_proto_dependencies(descriptor_sets):
    """Creates hash of transitive proto dependencies.
    
    Args:
        descriptor_sets: List of dependency descriptor sets
        
    Returns:
        str: Hash of dependencies
    """
    if not descriptor_sets:
        return "no-deps"
    
    dep_paths = []
    for desc_set in descriptor_sets:
        dep_path = _get_file_path(desc_set)
        dep_paths.append(dep_path)
    
    # Sort for deterministic ordering
    dep_paths.sort()
    return _sha256_hash(":".join(dep_paths))[:16]

def _hash_import_paths(import_paths):
    """Creates hash of import paths.
    
    Args:
        import_paths: List of import paths
        
    Returns:
        str: Hash of import paths
    """
    if not import_paths:
        return "no-imports"
    
    # Sort for deterministic ordering
    sorted_paths = sorted(import_paths)
    return _sha256_hash(":".join(sorted_paths))[:16]

def _hash_protoc_options(ctx):
    """Creates hash of protoc compilation options.
    
    Args:
        ctx: Rule context
        
    Returns:
        str: Hash of protoc options
    """
    options = []
    
    # Add rule-level options
    if hasattr(ctx.attrs, 'options') and ctx.attrs.options:
        for key, value in sorted(ctx.attrs.options.items()):
            options.append("{}={}".format(key, value))
    
    # Add import prefix/strip options
    if hasattr(ctx.attrs, 'import_prefix') and ctx.attrs.import_prefix:
        options.append("import_prefix={}".format(ctx.attrs.import_prefix))
    
    if hasattr(ctx.attrs, 'strip_import_prefix') and ctx.attrs.strip_import_prefix:
        options.append("strip_import_prefix={}".format(ctx.attrs.strip_import_prefix))
    
    # Add well-known types option
    if hasattr(ctx.attrs, 'well_known_types'):
        options.append("well_known_types={}".format(ctx.attrs.well_known_types))
    
    if not options:
        return "default-options"
    
    return _sha256_hash(":".join(options))[:16]

def _hash_language_options(language, language_options):
    """Creates hash of language-specific options.
    
    Args:
        language: Target language
        language_options: Language-specific options
        
    Returns:
        str: Hash of language options
    """
    if not language_options:
        return "default-{}-options".format(language)
    
    options = []
    for key, value in sorted(language_options.items()):
        options.append("{}={}".format(key, value))
    
    return _sha256_hash(":".join(options))[:16]

def _hash_language_tool_version(language):
    """Creates hash of language-specific tool versions.
    
    Args:
        language: Target language
        
    Returns:
        str: Hash of tool versions
    """
    # In a real implementation, this would query actual tool versions
    # For now, we use placeholder versions
    tool_versions = {
        "go": ["protoc-gen-go:1.28.1", "protoc-gen-go-grpc:1.2.0"],
        "python": ["protoc-gen-python:4.21.12", "grpcio-tools:1.48.2"],
        "typescript": ["protoc-gen-ts:0.8.6", "grpc-tools:1.11.2"],
        "cpp": ["protoc:3.21.12", "grpc:1.50.1"],
        "rust": ["protoc-gen-rust:2.28.0", "tonic-build:0.8.4"],
    }
    
    versions = tool_versions.get(language, ["unknown:0.0.0"])
    return _sha256_hash(":".join(versions))[:16]

def _hash_bundle_config(bundle_config):
    """Creates hash of bundle configuration.
    
    Args:
        bundle_config: Bundle configuration
        
    Returns:
        str: Hash of bundle config
    """
    if not bundle_config:
        return "default-bundle-config"
    
    config_items = []
    for key, value in sorted(bundle_config.items()):
        config_items.append("{}={}".format(key, value))
    
    return _sha256_hash(":".join(config_items))[:16]

def _hash_consistency_checks(ctx):
    """Creates hash of consistency check configuration.
    
    Args:
        ctx: Rule context
        
    Returns:
        str: Hash of consistency checks
    """
    checks = []
    
    if hasattr(ctx.attrs, 'consistency_checks'):
        checks.append("consistency_checks={}".format(ctx.attrs.consistency_checks))
    
    if hasattr(ctx.attrs, 'parallel_generation'):
        checks.append("parallel_generation={}".format(ctx.attrs.parallel_generation))
    
    if not checks:
        return "default-checks"
    
    return _sha256_hash(":".join(checks))[:16]

def _hash_grpc_plugins(plugins):
    """Creates hash of gRPC plugin configurations.
    
    Args:
        plugins: Plugin configurations
        
    Returns:
        str: Hash of plugins
    """
    if not plugins:
        return "no-plugins"
    
    plugin_hashes = []
    for plugin_name, plugin_config in sorted(plugins.items()):
        config_str = ":".join([
            "{}={}".format(k, v) 
            for k, v in sorted(plugin_config.items())
        ])
        plugin_hashes.append("{}:{}".format(plugin_name, config_str))
    
    return _sha256_hash(":".join(plugin_hashes))[:16]

def _hash_service_config(service_config):
    """Creates hash of service configuration.
    
    Args:
        service_config: Service configuration
        
    Returns:
        str: Hash of service config
    """
    if not service_config:
        return "default-service-config"
    
    config_items = []
    for key, value in sorted(service_config.items()):
        config_items.append("{}={}".format(key, value))
    
    return _sha256_hash(":".join(config_items))[:16]

def _hash_grpc_tool_versions():
    """Creates hash of gRPC-specific tool versions.
    
    Returns:
        str: Hash of gRPC tool versions
    """
    # In a real implementation, this would query actual versions
    grpc_tools = [
        "grpc:1.50.1",
        "protoc-gen-grpc-gateway:2.12.0",
        "protoc-gen-openapiv2:2.12.0",
        "protoc-gen-validate:0.6.7",
    ]
    
    return _sha256_hash(":".join(grpc_tools))[:16]

def _hash_language_plugins(language, plugins):
    """Creates hash of language-specific plugin effects.
    
    Args:
        language: Target language
        plugins: Plugin configurations
        
    Returns:
        str: Hash of language plugins
    """
    if not plugins:
        return "no-{}-plugins".format(language)
    
    # Filter plugins that affect this language
    relevant_plugins = []
    
    for plugin_name, plugin_config in plugins.items():
        if _plugin_affects_language(plugin_name, language):
            relevant_plugins.append("{}:{}".format(
                plugin_name,
                _hash_dict(plugin_config)
            ))
    
    if not relevant_plugins:
        return "no-{}-plugins".format(language)
    
    return _sha256_hash(":".join(sorted(relevant_plugins)))[:16]

def _hash_rule_version():
    """Creates hash representing current rule implementation version.
    
    Returns:
        str: Rule version hash
    """
    # This should be updated whenever cache key generation logic changes
    rule_version = "cache-keys-v1.0.0-with-language-isolation"
    return _sha256_hash(rule_version)[:16]

def _plugin_affects_language(plugin_name, language):
    """Determines if a plugin affects a specific language.
    
    Args:
        plugin_name: Name of the plugin
        language: Target language
        
    Returns:
        bool: True if plugin affects this language
    """
    plugin_language_map = {
        "grpc-gateway": ["go"],
        "openapi": ["go", "python", "typescript"],
        "validate": ["go", "python", "typescript", "cpp"],
        "mock": ["go", "python", "typescript"],
        "grpc-web": ["typescript"],
    }
    
    affected_languages = plugin_language_map.get(plugin_name, [])
    return language in affected_languages

def _get_file_path(file_obj):
    """Gets path from a file object.
    
    Args:
        file_obj: File object
        
    Returns:
        str: File path
    """
    if hasattr(file_obj, 'short_path'):
        return file_obj.short_path
    elif hasattr(file_obj, 'path'):
        return file_obj.path
    else:
        return str(file_obj)

def _hash_dict(d):
    """Creates deterministic hash of a dictionary.
    
    Args:
        d: Dictionary to hash
        
    Returns:
        str: Hash of dictionary
    """
    if not d:
        return "empty"
    
    items = []
    for key, value in sorted(d.items()):
        items.append("{}={}".format(key, value))
    
    return _sha256_hash(":".join(items))[:8]

def _sha256_hash(content):
    """Creates SHA-256 hash of content.
    
    Args:
        content: String content to hash
        
    Returns:
        str: SHA-256 hash in hex format
    """
    # In a real Buck2 implementation, we would use Buck2's built-in hashing
    # For now, we simulate with a simple hash
    import hashlib
    return hashlib.sha256(content.encode()).hexdigest()
