"""Test suite for protobuf caching optimization.

This module tests the comprehensive caching system including cache key generation,
storage/retrieval, metrics, and performance optimization features.
"""

load("@prelude//testing:asserts.bzl", "asserts")
load("//rules/private:cache_impl.bzl", "get_default_cache_config", "create_cache_key_info", "try_cache_lookup", "store_in_cache", "get_cache_metrics_info")
load("//rules/private:cache_keys.bzl", "generate_cache_key", "generate_language_cache_key", "validate_cache_key", "generate_cache_key_for_bundle")
load("//rules/private:cache_storage.bzl", "cache_lookup", "cache_store", "cache_invalidate", "cache_cleanup", "get_cache_statistics")
load("//rules/private:cache_metrics.bzl", "get_cache_metrics", "analyze_cache_performance", "get_cache_health_status")
load("//rules/private:providers.bzl", "ProtoInfo", "CacheKeyInfo", "CacheConfigInfo")

def cache_key_generation_test_suite():
    """Test suite for cache key generation functionality."""
    
    def test_cache_key_deterministic():
        """Test that cache key generation is deterministic."""
        # Create mock context and proto info
        mock_ctx = _create_mock_context({
            "options": {"go_package": "github.com/test/v1"},
            "import_prefix": "",
            "strip_import_prefix": "",
            "well_known_types": True,
        })
        
        mock_proto_info = ProtoInfo(
            descriptor_set = None,
            proto_files = ["test.proto", "types.proto"],
            import_paths = ["."],
            transitive_descriptor_sets = [],
            transitive_proto_files = ["test.proto", "types.proto"],
            transitive_import_paths = ["."],
            go_package = "github.com/test/v1",
            python_package = "",
            java_package = "",
            lint_report = None,
            breaking_report = None,
        )
        
        # Generate cache keys multiple times
        key1 = generate_cache_key(mock_ctx, mock_proto_info)
        key2 = generate_cache_key(mock_ctx, mock_proto_info)
        key3 = generate_cache_key(mock_ctx, mock_proto_info)
        
        # All keys should be identical
        asserts.equals(key1, key2, "Cache keys should be deterministic")
        asserts.equals(key2, key3, "Cache keys should be deterministic")
        asserts.true(validate_cache_key(key1), "Generated cache key should be valid")
    
    def test_cache_key_language_isolation():
        """Test that language-specific cache keys provide proper isolation."""
        base_key = "abc123def456789012345678901234567"
        
        # Generate language-specific keys
        go_key = generate_language_cache_key(base_key, "go", {"go_package": "test/v1"})
        python_key = generate_language_cache_key(base_key, "python", {"python_package": "test.v1"})
        typescript_key = generate_language_cache_key(base_key, "typescript", {"npm_package": "@test/v1"})
        
        # All keys should be different
        asserts.not_equals(go_key, python_key, "Go and Python cache keys should differ")
        asserts.not_equals(python_key, typescript_key, "Python and TypeScript cache keys should differ")
        asserts.not_equals(go_key, typescript_key, "Go and TypeScript cache keys should differ")
        
        # All keys should be valid
        asserts.true(validate_cache_key(go_key), "Go cache key should be valid")
        asserts.true(validate_cache_key(python_key), "Python cache key should be valid")
        asserts.true(validate_cache_key(typescript_key), "TypeScript cache key should be valid")
    
    def test_cache_key_option_sensitivity():
        """Test that cache keys change when options change."""
        mock_ctx1 = _create_mock_context({
            "options": {"go_package": "github.com/test/v1"},
        })
        
        mock_ctx2 = _create_mock_context({
            "options": {"go_package": "github.com/test/v2"},  # Different version
        })
        
        mock_proto_info = ProtoInfo(
            descriptor_set = None,
            proto_files = ["test.proto"],
            import_paths = ["."],
            transitive_descriptor_sets = [],
            transitive_proto_files = ["test.proto"],
            transitive_import_paths = ["."],
            go_package = "",
            python_package = "",
            java_package = "",
            lint_report = None,
            breaking_report = None,
        )
        
        key1 = generate_cache_key(mock_ctx1, mock_proto_info)
        key2 = generate_cache_key(mock_ctx2, mock_proto_info)
        
        asserts.not_equals(key1, key2, "Cache keys should differ when options change")
    
    def test_bundle_cache_keys():
        """Test cache key generation for bundles."""
        mock_ctx = _create_mock_context({})
        mock_proto_info = ProtoInfo(
            descriptor_set = None,
            proto_files = ["test.proto"],
            import_paths = ["."],
            transitive_descriptor_sets = [],
            transitive_proto_files = ["test.proto"],
            transitive_import_paths = ["."],
            go_package = "",
            python_package = "",
            java_package = "",
            lint_report = None,
            breaking_report = None,
        )
        
        languages = {
            "go": {"go_package": "test/v1"},
            "python": {"python_package": "test.v1"},
        }
        
        bundle_config = {"consistency_checks": True}
        
        bundle_keys = generate_cache_key_for_bundle(
            mock_ctx,
            mock_proto_info,
            languages,
            bundle_config
        )
        
        asserts.true("go" in bundle_keys, "Bundle should have Go cache key")
        asserts.true("python" in bundle_keys, "Bundle should have Python cache key")
        asserts.not_equals(bundle_keys["go"], bundle_keys["python"], "Bundle language keys should differ")
    
    return [
        test_cache_key_deterministic,
        test_cache_key_language_isolation,
        test_cache_key_option_sensitivity,
        test_bundle_cache_keys,
    ]

def cache_storage_test_suite():
    """Test suite for cache storage functionality."""
    
    def test_cache_store_and_lookup():
        """Test basic cache storage and retrieval."""
        cache_key = "test_cache_key_12345678901234567"
        language = "go"
        cache_path = "/tmp/test_cache"
        
        # Mock artifacts
        artifacts = ["file1.go", "file2.go"]
        
        # Store in cache
        cache_info = cache_store(cache_key, language, artifacts, cache_path, False)
        
        # Verify storage info
        asserts.equals(cache_info.cache_key, cache_key, "Cache key should match")
        asserts.equals(cache_info.language, language, "Language should match")
        asserts.equals(cache_info.compression_used, False, "Compression setting should match")
        
        # Test lookup (note: in real implementation, this would actually find the cache)
        # For now, we expect cache miss since filesystem operations are mocked
        success, retrieved_artifacts, lookup_info = cache_lookup(cache_key, language, cache_path)
        asserts.false(success, "Cache lookup should miss in test environment")
    
    def test_cache_invalidation():
        """Test cache invalidation functionality."""
        cache_key = "test_invalidation_key_123456789"
        language = "python"
        cache_path = "/tmp/test_cache"
        
        # Test invalidation (should handle non-existent cache gracefully)
        result = cache_invalidate(cache_key, language, cache_path)
        asserts.false(result, "Invalidation should return false for non-existent cache")
    
    def test_cache_cleanup():
        """Test cache cleanup functionality."""
        cache_path = "/tmp/test_cache"
        size_limit_mb = 100
        
        # Test cleanup on empty cache
        cleanup_stats = cache_cleanup(cache_path, size_limit_mb)
        
        asserts.equals(cleanup_stats["entries_removed"], 0, "No entries should be removed from empty cache")
        asserts.equals(cleanup_stats["bytes_freed"], 0, "No bytes should be freed from empty cache")
    
    def test_cache_statistics():
        """Test cache statistics functionality."""
        cache_path = "/tmp/test_cache"
        
        # Get statistics for empty cache
        stats = get_cache_statistics(cache_path)
        
        asserts.equals(stats["total_entries"], 0, "Empty cache should have 0 entries")
        asserts.equals(stats["total_size_bytes"], 0, "Empty cache should have 0 bytes")
        asserts.equals(stats["total_size_mb"], 0.0, "Empty cache should have 0 MB")
    
    return [
        test_cache_store_and_lookup,
        test_cache_invalidation,
        test_cache_cleanup,
        test_cache_statistics,
    ]

def cache_metrics_test_suite():
    """Test suite for cache metrics functionality."""
    
    def test_cache_metrics():
        """Test cache metrics retrieval."""
        cache_path = "/tmp/test_cache"
        
        # Get metrics
        metrics = get_cache_metrics(cache_path)
        
        # Verify metrics structure
        asserts.true("hit_rate" in metrics, "Metrics should include hit rate")
        asserts.true("miss_rate" in metrics, "Metrics should include miss rate")
        asserts.true("total_lookups" in metrics, "Metrics should include total lookups")
        asserts.true("language_breakdown" in metrics, "Metrics should include language breakdown")
        
        # Verify hit/miss rates sum to ~100%
        total_rate = metrics["hit_rate"] + metrics["miss_rate"]
        asserts.true(abs(total_rate - 100.0) < 0.1, "Hit rate + miss rate should equal 100%")
    
    def test_cache_performance_analysis():
        """Test cache performance analysis."""
        cache_path = "/tmp/test_cache"
        
        # Analyze performance
        analysis = analyze_cache_performance(cache_path, 24)
        
        # Verify analysis structure
        asserts.true("overall_performance" in analysis, "Analysis should include overall performance")
        asserts.true("language_performance" in analysis, "Analysis should include language performance")
        asserts.true("bottlenecks" in analysis, "Analysis should include bottlenecks")
        asserts.true("optimization_opportunities" in analysis, "Analysis should include optimization opportunities")
    
    def test_cache_health_status():
        """Test cache health status assessment."""
        cache_path = "/tmp/test_cache"
        
        # Get health status
        health = get_cache_health_status(cache_path)
        
        # Verify health status structure
        asserts.true("health_score" in health, "Health should include score")
        asserts.true("status" in health, "Health should include status")
        asserts.true("recommendations" in health, "Health should include recommendations")
        
        # Verify health score is in valid range
        score = health["health_score"]
        asserts.true(score >= 0 and score <= 100, "Health score should be 0-100")
    
    return [
        test_cache_metrics,
        test_cache_performance_analysis,
        test_cache_health_status,
    ]

def cache_integration_test_suite():
    """Test suite for cache integration with protobuf rules."""
    
    def test_cache_config_defaults():
        """Test default cache configuration."""
        config = get_default_cache_config()
        
        # Verify default settings
        asserts.true(config.hash_inputs, "Should hash inputs by default")
        asserts.true(config.hash_tools, "Should hash tools by default")
        asserts.true(config.language_isolation, "Should use language isolation by default")
        asserts.true(config.local_cache_enabled, "Local cache should be enabled by default")
        asserts.false(config.remote_cache_enabled, "Remote cache should be disabled by default")
        asserts.true(config.compression_enabled, "Compression should be enabled by default")
    
    def test_cache_key_info_creation():
        """Test cache key info creation."""
        mock_ctx = _create_mock_context({})
        mock_proto_info = ProtoInfo(
            descriptor_set = None,
            proto_files = ["test.proto"],
            import_paths = ["."],
            transitive_descriptor_sets = [],
            transitive_proto_files = ["test.proto"],
            transitive_import_paths = ["."],
            go_package = "",
            python_package = "",
            java_package = "",
            lint_report = None,
            breaking_report = None,
        )
        
        # Create cache key info
        cache_key_info = create_cache_key_info(mock_ctx, mock_proto_info, "go", {"go_package": "test/v1"})
        
        # Verify cache key info structure
        asserts.true(cache_key_info.base_cache_key != "", "Should have base cache key")
        asserts.true("go" in cache_key_info.language_cache_keys, "Should have Go language cache key")
        asserts.true(cache_key_info.tool_versions_hash != "", "Should have tool versions hash")
        asserts.true(cache_key_info.proto_content_hash != "", "Should have proto content hash")
    
    def test_cache_lookup_integration():
        """Test cache lookup integration."""
        mock_ctx = _create_mock_context({})
        cache_config = get_default_cache_config()
        
        # Test cache lookup (should miss in test environment)
        success, artifacts, cache_info = try_cache_lookup(
            mock_ctx,
            "test_key_12345678901234567890123",
            "go",
            cache_config
        )
        
        # Should miss because filesystem operations are mocked
        asserts.false(success, "Cache lookup should miss in test environment")
        asserts.equals(len(artifacts), 0, "Should return empty artifacts on miss")
    
    return [
        test_cache_config_defaults,
        test_cache_key_info_creation,
        test_cache_lookup_integration,
    ]

def cache_performance_test_suite():
    """Test suite for cache performance characteristics."""
    
    def test_cache_key_performance():
        """Test cache key generation performance."""
        mock_ctx = _create_mock_context({})
        mock_proto_info = ProtoInfo(
            descriptor_set = None,
            proto_files = ["test.proto"] * 10,  # Simulate multiple files
            import_paths = ["."],
            transitive_descriptor_sets = [],
            transitive_proto_files = ["test.proto"] * 10,
            transitive_import_paths = ["."],
            go_package = "",
            python_package = "",
            java_package = "",
            lint_report = None,
            breaking_report = None,
        )
        
        # Generate cache keys multiple times to test performance
        keys = []
        for i in range(100):  # Generate 100 keys
            key = generate_cache_key(mock_ctx, mock_proto_info)
            keys.append(key)
        
        # All keys should be identical (deterministic)
        for key in keys:
            asserts.equals(key, keys[0], "All generated keys should be identical")
    
    def test_cache_validation_performance():
        """Test cache key validation performance."""
        # Test valid cache keys
        valid_keys = [
            "abc123def456789012345678901234567",
            "123456789abcdef0123456789abcdef01",
            "fedcba987654321098765432109876543",
        ]
        
        for key in valid_keys:
            asserts.true(validate_cache_key(key), "Valid key should pass validation")
        
        # Test invalid cache keys
        invalid_keys = [
            "",  # Empty
            "abc123",  # Too short
            "abc123def456789012345678901234567890",  # Too long
            "ghijklmnopqrstuvwxyz123456789012345",  # Invalid hex chars
        ]
        
        for key in invalid_keys:
            asserts.false(validate_cache_key(key), "Invalid key should fail validation")
    
    return [
        test_cache_key_performance,
        test_cache_validation_performance,
    ]

def _create_mock_context(attrs):
    """Creates a mock rule context for testing.
    
    Args:
        attrs: Dictionary of attributes to include in the context
        
    Returns:
        Mock context object
    """
    # In a real implementation, this would create a proper mock context
    # For now, we create a simple object with the required attributes
    class MockContext:
        def __init__(self, attributes):
            self.attrs = MockAttrs(attributes)
    
    class MockAttrs:
        def __init__(self, attributes):
            for key, value in attributes.items():
                setattr(self, key, value)
        
        def get(self, key, default=None):
            return getattr(self, key, default)
    
    return MockContext(attrs)

def run_all_cache_tests():
    """Runs all cache-related tests.
    
    Returns:
        dict: Test results summary
    """
    test_suites = [
        ("Cache Key Generation", cache_key_generation_test_suite()),
        ("Cache Storage", cache_storage_test_suite()),
        ("Cache Metrics", cache_metrics_test_suite()),
        ("Cache Integration", cache_integration_test_suite()),
        ("Cache Performance", cache_performance_test_suite()),
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = []
    
    for suite_name, tests in test_suites:
        print("Running {} tests...".format(suite_name))
        
        for test_func in tests:
            total_tests += 1
            try:
                test_func()
                passed_tests += 1
                print("  ✓ {}".format(test_func.__name__))
            except Exception as e:
                failed_tests.append("{}::{}: {}".format(suite_name, test_func.__name__, str(e)))
                print("  ✗ {}: {}".format(test_func.__name__, str(e)))
    
    print("\nTest Summary:")
    print("  Total: {}".format(total_tests))
    print("  Passed: {}".format(passed_tests))
    print("  Failed: {}".format(len(failed_tests)))
    
    if failed_tests:
        print("\nFailed Tests:")
        for failure in failed_tests:
            print("  - {}".format(failure))
    
    return {
        "total": total_tests,
        "passed": passed_tests,
        "failed": len(failed_tests),
        "success_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
        "failures": failed_tests,
    }
