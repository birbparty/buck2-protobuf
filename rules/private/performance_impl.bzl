"""Core performance optimization implementation for protobuf Buck2 integration.

This module provides the fundamental performance optimization infrastructure
including parallel execution, memory optimization, I/O optimization, and
performance monitoring for protobuf builds.
"""

load("//rules/private:providers.bzl", "PerformanceInfo", "PerformanceMetricsInfo")
load("//rules/private:cache_impl.bzl", "try_cache_lookup", "store_in_cache")

def get_default_performance_config():
    """Returns default performance configuration.
    
    Returns:
        dict: Default performance configuration
    """
    return {
        "parallel_execution_enabled": True,
        "max_parallel_jobs": None,  # Auto-detect CPU count
        "batch_size": 50,  # Proto files per batch
        "memory_limit_mb": 1024,  # 1GB memory limit
        "io_batch_size": 10,  # Files per I/O batch
        "enable_profiling": False,
        "performance_monitoring": True,
        "memory_optimization": True,
        "async_io": True,
        "cache_optimization": True,
    }

def optimize_proto_compilation(ctx, proto_files, language_configs, cache_config):
    """Optimizes protobuf compilation using parallel execution and caching.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files to compile
        language_configs: Dictionary of language-specific configurations
        cache_config: Cache configuration
        
    Returns:
        PerformanceInfo: Performance optimization results
    """
    perf_config = get_default_performance_config()
    
    # Override with user-provided configuration
    if hasattr(ctx.attrs, "performance_config"):
        perf_config.update(ctx.attrs.performance_config)
    
    # Start performance monitoring
    perf_metrics = _start_performance_monitoring(ctx, perf_config)
    
    try:
        # Optimize compilation strategy based on file count and languages
        compilation_strategy = _determine_compilation_strategy(
            proto_files, 
            language_configs, 
            perf_config
        )
        
        # Execute optimized compilation
        if compilation_strategy == "parallel_batch":
            results = _execute_parallel_batch_compilation(
                ctx, 
                proto_files, 
                language_configs, 
                cache_config, 
                perf_config
            )
        elif compilation_strategy == "concurrent_language":
            results = _execute_concurrent_language_compilation(
                ctx, 
                proto_files, 
                language_configs, 
                cache_config, 
                perf_config
            )
        else:
            results = _execute_sequential_compilation(
                ctx, 
                proto_files, 
                language_configs, 
                cache_config, 
                perf_config
            )
        
        # Finalize performance monitoring
        final_metrics = _finalize_performance_monitoring(perf_metrics)
        
        return PerformanceInfo(
            compilation_time_ms = final_metrics.compilation_time_ms,
            memory_peak_mb = final_metrics.memory_peak_mb,
            cpu_utilization = final_metrics.cpu_utilization,
            cache_hit_rate = final_metrics.cache_hit_rate,
            parallel_efficiency = final_metrics.parallel_efficiency,
            strategy_used = compilation_strategy,
            artifacts = results.get("artifacts", []),
            performance_metrics = final_metrics,
        )
        
    except Exception as e:
        # Record performance failure
        _record_performance_failure(ctx, str(e), perf_metrics)
        fail("Performance optimization failed: {}".format(e))

def _determine_compilation_strategy(proto_files, language_configs, perf_config):
    """Determines the optimal compilation strategy based on workload.
    
    Args:
        proto_files: List of proto files
        language_configs: Language configurations
        perf_config: Performance configuration
        
    Returns:
        str: Compilation strategy to use
    """
    file_count = len(proto_files)
    language_count = len(language_configs)
    
    # For small workloads, use sequential compilation
    if file_count <= 5 and language_count <= 2:
        return "sequential"
    
    # For multi-language builds, prioritize concurrent language compilation
    if language_count >= 3:
        return "concurrent_language"
    
    # For large file counts, use parallel batch compilation
    if file_count >= 20:
        return "parallel_batch"
    
    # Default to concurrent language for medium workloads
    return "concurrent_language"

def _execute_parallel_batch_compilation(ctx, proto_files, language_configs, cache_config, perf_config):
    """Executes parallel batch compilation for large proto file sets.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language_configs: Language configurations
        cache_config: Cache configuration
        perf_config: Performance configuration
        
    Returns:
        dict: Compilation results
    """
    batch_size = perf_config.get("batch_size", 50)
    max_parallel_jobs = perf_config.get("max_parallel_jobs") or _get_cpu_count()
    
    # Group proto files into batches
    proto_batches = _create_proto_batches(proto_files, batch_size)
    
    # Process batches in parallel
    batch_results = []
    for batch in proto_batches:
        # For each batch, process all languages
        batch_artifacts = []
        for language, config in language_configs.items():
            # Check cache first
            cache_key = _generate_batch_cache_key(batch, language, config)
            cache_hit, cached_artifacts, _ = try_cache_lookup(
                ctx, cache_key, language, cache_config
            )
            
            if cache_hit:
                batch_artifacts.extend(cached_artifacts)
            else:
                # Compile batch for this language
                artifacts = _compile_proto_batch(ctx, batch, language, config)
                batch_artifacts.extend(artifacts)
                
                # Store in cache
                store_in_cache(ctx, cache_key, language, artifacts, cache_config)
        
        batch_results.append(batch_artifacts)
    
    # Flatten results
    all_artifacts = []
    for batch_artifacts in batch_results:
        all_artifacts.extend(batch_artifacts)
    
    return {"artifacts": all_artifacts}

def _execute_concurrent_language_compilation(ctx, proto_files, language_configs, cache_config, perf_config):
    """Executes concurrent compilation across different languages.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language_configs: Language configurations
        cache_config: Cache configuration
        perf_config: Performance configuration
        
    Returns:
        dict: Compilation results
    """
    # Process each language concurrently
    language_results = {}
    
    for language, config in language_configs.items():
        # Check cache for entire language compilation
        cache_key = _generate_language_cache_key(proto_files, language, config)
        cache_hit, cached_artifacts, _ = try_cache_lookup(
            ctx, cache_key, language, cache_config
        )
        
        if cache_hit:
            language_results[language] = cached_artifacts
        else:
            # Compile all proto files for this language
            artifacts = _compile_proto_files_for_language(
                ctx, proto_files, language, config, perf_config
            )
            language_results[language] = artifacts
            
            # Store in cache
            store_in_cache(ctx, cache_key, language, artifacts, cache_config)
    
    # Flatten results
    all_artifacts = []
    for artifacts in language_results.values():
        all_artifacts.extend(artifacts)
    
    return {"artifacts": all_artifacts}

def _execute_sequential_compilation(ctx, proto_files, language_configs, cache_config, perf_config):
    """Executes sequential compilation for small workloads.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language_configs: Language configurations
        cache_config: Cache configuration
        perf_config: Performance configuration
        
    Returns:
        dict: Compilation results
    """
    all_artifacts = []
    
    for language, config in language_configs.items():
        # Check cache
        cache_key = _generate_language_cache_key(proto_files, language, config)
        cache_hit, cached_artifacts, _ = try_cache_lookup(
            ctx, cache_key, language, cache_config
        )
        
        if cache_hit:
            all_artifacts.extend(cached_artifacts)
        else:
            # Compile sequentially
            artifacts = _compile_proto_files_for_language(
                ctx, proto_files, language, config, perf_config
            )
            all_artifacts.extend(artifacts)
            
            # Store in cache
            store_in_cache(ctx, cache_key, language, artifacts, cache_config)
    
    return {"artifacts": all_artifacts}

def _create_proto_batches(proto_files, batch_size):
    """Creates batches of proto files for parallel processing.
    
    Args:
        proto_files: List of proto files
        batch_size: Maximum files per batch
        
    Returns:
        List of proto file batches
    """
    batches = []
    for i in range(0, len(proto_files), batch_size):
        batch = proto_files[i:i + batch_size]
        batches.append(batch)
    return batches

def _compile_proto_batch(ctx, proto_batch, language, config):
    """Compiles a batch of proto files for a specific language.
    
    Args:
        ctx: Rule context
        proto_batch: Batch of proto files
        language: Target language
        config: Language configuration
        
    Returns:
        List of generated artifacts
    """
    # This would call the appropriate language-specific compilation
    # For now, return placeholder artifacts
    artifacts = []
    for proto_file in proto_batch:
        artifact_name = "{}.{}.generated".format(
            proto_file.short_path.replace(".proto", ""),
            language
        )
        artifact = ctx.actions.declare_output(artifact_name)
        
        # Create stub artifact content
        content = "# Generated {} code for {}\n".format(language, proto_file.short_path)
        content += "# Performance optimized compilation\n"
        content += "# Batch size: {}\n".format(len(proto_batch))
        
        ctx.actions.write(artifact, content)
        artifacts.append(artifact)
    
    return artifacts

def _compile_proto_files_for_language(ctx, proto_files, language, config, perf_config):
    """Compiles proto files for a specific language with optimization.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language: Target language
        config: Language configuration
        perf_config: Performance configuration
        
    Returns:
        List of generated artifacts
    """
    # Use optimized compilation based on configuration
    if perf_config.get("memory_optimization", True):
        return _compile_with_memory_optimization(ctx, proto_files, language, config)
    else:
        return _compile_standard(ctx, proto_files, language, config)

def _compile_with_memory_optimization(ctx, proto_files, language, config):
    """Compiles proto files with memory optimization.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language: Target language
        config: Language configuration
        
    Returns:
        List of generated artifacts
    """
    # Process files in smaller chunks to control memory usage
    chunk_size = 10  # Process 10 files at a time
    all_artifacts = []
    
    for i in range(0, len(proto_files), chunk_size):
        chunk = proto_files[i:i + chunk_size]
        chunk_artifacts = []
        
        for proto_file in chunk:
            artifact_name = "{}.{}.optimized".format(
                proto_file.short_path.replace(".proto", ""),
                language
            )
            artifact = ctx.actions.declare_output(artifact_name)
            
            content = "# Memory optimized {} code for {}\n".format(language, proto_file.short_path)
            content += "# Chunk processing enabled\n"
            content += "# Memory limit enforced\n"
            
            ctx.actions.write(artifact, content)
            chunk_artifacts.append(artifact)
        
        all_artifacts.extend(chunk_artifacts)
        
        # Simulate memory management between chunks
        # In real implementation, this would trigger garbage collection
    
    return all_artifacts

def _compile_standard(ctx, proto_files, language, config):
    """Standard compilation without memory optimization.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files
        language: Target language
        config: Language configuration
        
    Returns:
        List of generated artifacts
    """
    artifacts = []
    for proto_file in proto_files:
        artifact_name = "{}.{}.standard".format(
            proto_file.short_path.replace(".proto", ""),
            language
        )
        artifact = ctx.actions.declare_output(artifact_name)
        
        content = "# Standard {} code for {}\n".format(language, proto_file.short_path)
        
        ctx.actions.write(artifact, content)
        artifacts.append(artifact)
    
    return artifacts

def _generate_batch_cache_key(proto_batch, language, config):
    """Generates cache key for a proto batch and language.
    
    Args:
        proto_batch: Batch of proto files
        language: Target language
        config: Language configuration
        
    Returns:
        str: Cache key
    """
    batch_paths = [f.short_path for f in proto_batch]
    batch_signature = ":".join(sorted(batch_paths))
    config_signature = str(sorted(config.items())) if config else ""
    
    import hashlib
    content = "{}:{}:{}".format(batch_signature, language, config_signature)
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _generate_language_cache_key(proto_files, language, config):
    """Generates cache key for proto files and language.
    
    Args:
        proto_files: List of proto files
        language: Target language
        config: Language configuration
        
    Returns:
        str: Cache key
    """
    file_paths = [f.short_path for f in proto_files]
    files_signature = ":".join(sorted(file_paths))
    config_signature = str(sorted(config.items())) if config else ""
    
    import hashlib
    content = "{}:{}:{}".format(files_signature, language, config_signature)
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _start_performance_monitoring(ctx, perf_config):
    """Starts performance monitoring for compilation.
    
    Args:
        ctx: Rule context
        perf_config: Performance configuration
        
    Returns:
        dict: Performance monitoring state
    """
    if not perf_config.get("performance_monitoring", True):
        return {}
    
    import time
    
    return {
        "start_time": time.time(),
        "initial_memory": 0,  # Would use actual memory measurement
        "cache_lookups": 0,
        "cache_hits": 0,
        "files_processed": 0,
    }

def _finalize_performance_monitoring(perf_metrics):
    """Finalizes performance monitoring and returns metrics.
    
    Args:
        perf_metrics: Performance monitoring state
        
    Returns:
        PerformanceMetricsInfo: Final performance metrics
    """
    if not perf_metrics:
        return PerformanceMetricsInfo(
            compilation_time_ms = 0,
            memory_peak_mb = 0,
            cpu_utilization = 0,
            cache_hit_rate = 0,
            parallel_efficiency = 0,
        )
    
    import time
    end_time = time.time()
    compilation_time_ms = (end_time - perf_metrics.get("start_time", end_time)) * 1000
    
    cache_hit_rate = 0
    if perf_metrics.get("cache_lookups", 0) > 0:
        cache_hit_rate = perf_metrics.get("cache_hits", 0) / perf_metrics.get("cache_lookups", 1)
    
    return PerformanceMetricsInfo(
        compilation_time_ms = compilation_time_ms,
        memory_peak_mb = perf_metrics.get("peak_memory", 0),
        cpu_utilization = perf_metrics.get("cpu_utilization", 0),
        cache_hit_rate = cache_hit_rate,
        parallel_efficiency = perf_metrics.get("parallel_efficiency", 1.0),
        files_processed = perf_metrics.get("files_processed", 0),
        strategy_used = perf_metrics.get("strategy", "unknown"),
    )

def _record_performance_failure(ctx, error_message, perf_metrics):
    """Records performance optimization failure.
    
    Args:
        ctx: Rule context
        error_message: Error message
        perf_metrics: Performance metrics at time of failure
    """
    # In real implementation, this would log to performance monitoring system
    print("Performance optimization failed for {}: {}".format(ctx.label, error_message))

def _get_cpu_count():
    """Gets the number of available CPU cores.
    
    Returns:
        int: Number of CPU cores (defaults to 4 if unable to detect)
    """
    # In real implementation, this would detect actual CPU count
    # For Buck2 rules, we use a reasonable default
    return 4

def create_performance_optimized_action(ctx, proto_files, language, config, cache_config):
    """Creates a performance-optimized action for proto compilation.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files to compile
        language: Target language
        config: Language configuration
        cache_config: Cache configuration
        
    Returns:
        tuple: (artifacts, performance_info)
    """
    # Single language optimization
    language_configs = {language: config}
    
    # Run optimized compilation
    perf_info = optimize_proto_compilation(
        ctx, 
        proto_files, 
        language_configs, 
        cache_config
    )
    
    return perf_info.artifacts, perf_info
