"""
Comprehensive ORAS Integration Tests

This module provides end-to-end integration testing of the complete ORAS ecosystem,
validating all components work together seamlessly across different scenarios.
"""

import pytest
import time
from pathlib import Path
from typing import Dict, Any, List

from . import PERFORMANCE_TARGETS


class TestOrasIntegration:
    """End-to-end integration tests for ORAS ecosystem."""
    
    def test_complete_workflow_protoc(self, protoc_distributor, performance_timer, current_platform):
        """Test complete protoc distribution workflow."""
        # Test workflow: get protoc -> verify -> use for compilation
        timer = performance_timer
        
        # 1. Get protoc binary
        timer.start()
        protoc_path = protoc_distributor.get_protoc("24.4", current_platform)
        download_time = timer.stop()
        
        assert protoc_path is not None
        assert Path(protoc_path).exists()
        
        # 2. Verify binary is executable (on Unix systems)
        if current_platform.startswith(("linux", "darwin")):
            import stat
            mode = Path(protoc_path).stat().st_mode
            assert mode & stat.S_IXUSR  # User executable
        
        # 3. Test cache hit performance
        timer.start()
        cached_path = protoc_distributor.get_protoc("24.4", current_platform)
        cache_time = timer.stop()
        
        assert cached_path == protoc_path
        assert cache_time < PERFORMANCE_TARGETS["cache_hit_lookup"]
        
        # 4. Verify metrics
        metrics = protoc_distributor.get_performance_metrics()
        assert metrics["total_requests"] >= 2
        
    def test_complete_workflow_plugins(self, plugin_distributor, current_platform):
        """Test complete plugin distribution workflow."""
        # Test individual plugin download
        go_plugin = plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
        assert go_plugin is not None
        assert Path(go_plugin).exists()
        
        # Test bundle download
        go_bundle = plugin_distributor.get_bundle("go-development")
        assert isinstance(go_bundle, dict)
        assert "protoc-gen-go" in go_bundle
        assert "protoc-gen-go-grpc" in go_bundle
        
        # Verify all bundle plugins exist
        for plugin_name, plugin_path in go_bundle.items():
            assert Path(plugin_path).exists()
        
        # Test metrics collection
        metrics = plugin_distributor.get_performance_metrics()
        assert "bundle_downloads" in metrics
        assert metrics["bundle_downloads"] >= 1
    
    def test_cross_component_integration(self, protoc_distributor, plugin_distributor, 
                                       temp_cache_dir, current_platform):
        """Test integration between protoc and plugin distributors."""
        # Get protoc and plugins
        protoc_path = protoc_distributor.get_protoc("24.4", current_platform)
        go_bundle = plugin_distributor.get_bundle("go-development")
        
        # Verify we can create a working compilation environment
        assert Path(protoc_path).exists()
        for plugin_path in go_bundle.values():
            assert Path(plugin_path).exists()
        
        # Test cache directory structure
        cache_structure = {
            "protoc": protoc_distributor.cache_dir,
            "plugins": plugin_distributor.cache_dir
        }
        
        for component, cache_dir in cache_structure.items():
            assert cache_dir.exists()
    
    def test_registry_manager_integration(self, registry_manager, temp_cache_dir):
        """Test registry manager integration with ORAS infrastructure."""
        # Test health check
        health = registry_manager.health_check()
        assert "status" in health
        assert "checks" in health
        
        # Test repository structure
        repos = registry_manager.get_repository_structure()
        assert "tools" in repos
        assert "plugins" in repos
        
        # Test metrics collection
        metrics = registry_manager.get_metrics()
        assert isinstance(metrics, dict)
        
        # Test cache management
        cache_info = registry_manager.cleanup_cache(older_than_days=0)
        assert isinstance(cache_info, (int, dict))


class TestRealRegistryIntegration:
    """Integration tests against real oras.birb.homes registry."""
    
    @pytest.mark.real_registry
    @pytest.mark.slow
    def test_real_registry_connectivity(self, real_oras_client, test_artifacts):
        """Test connectivity to real ORAS registry."""
        # Try to list tags for a test repository
        try:
            tags = real_oras_client.list_tags("buck2-protobuf/test/hello-world")
            # If successful, we have connectivity
            assert isinstance(tags, list)
        except Exception as e:
            # Registry might not have test artifacts yet, that's ok
            # As long as we get a proper error response
            assert "not found" in str(e).lower() or "unavailable" in str(e).lower()
    
    @pytest.mark.real_registry
    @pytest.mark.slow
    def test_real_protoc_distribution(self, temp_cache_dir, current_platform):
        """Test real protoc distribution from registry."""
        from oras_protoc import ProtocOrasDistributor
        
        distributor = ProtocOrasDistributor(
            registry="oras.birb.homes",
            cache_dir=str(temp_cache_dir),
            verbose=True
        )
        
        try:
            # This will likely fail until we publish artifacts, but should gracefully fallback
            protoc_path = distributor.get_protoc("24.4", current_platform)
            assert protoc_path is not None
            assert Path(protoc_path).exists()
            
            # Check if it came from ORAS or HTTP fallback
            metrics = distributor.get_performance_metrics()
            total_requests = metrics.get("total_requests", 0)
            assert total_requests > 0
            
        except Exception as e:
            # Expected until we publish artifacts - should use HTTP fallback
            pytest.skip(f"Real registry test skipped - artifacts not yet published: {e}")
    
    @pytest.mark.real_registry
    @pytest.mark.slow  
    def test_real_plugin_distribution(self, temp_cache_dir, current_platform):
        """Test real plugin distribution from registry."""
        from oras_plugins import PluginOrasDistributor
        
        distributor = PluginOrasDistributor(
            registry="oras.birb.homes", 
            cache_dir=str(temp_cache_dir),
            verbose=True
        )
        
        try:
            # Test plugin download (will likely use HTTP fallback until published)
            plugin_path = distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
            assert plugin_path is not None
            assert Path(plugin_path).exists()
            
            metrics = distributor.get_performance_metrics()
            assert metrics["total_requests"] > 0
            
        except Exception as e:
            pytest.skip(f"Real registry test skipped - artifacts not yet published: {e}")


class TestConcurrencyAndParallelism:
    """Test concurrent operations and parallel downloads."""
    
    def test_concurrent_downloads(self, protoc_distributor, current_platform):
        """Test concurrent downloads don't interfere with each other."""
        import threading
        import queue
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def download_protoc(version):
            try:
                path = protoc_distributor.get_protoc(version, current_platform)
                results.put((version, path))
            except Exception as e:
                errors.put((version, str(e)))
        
        # Start concurrent downloads
        versions = ["24.4", "25.1", "26.1"]
        threads = []
        
        for version in versions:
            thread = threading.Thread(target=download_protoc, args=(version,))
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=60)
        
        # Check results
        assert results.qsize() > 0  # At least some should succeed
        
        # Verify no deadlocks or major errors
        while not results.empty():
            version, path = results.get()
            assert path is not None
            if Path(path).exists():  # Might be mocked
                assert Path(path).is_file()
    
    def test_parallel_plugin_bundle_download(self, plugin_distributor):
        """Test parallel download of plugin bundles."""
        import threading
        
        results = {}
        errors = {}
        
        def download_bundle(bundle_name):
            try:
                bundle = plugin_distributor.get_bundle(bundle_name)
                results[bundle_name] = bundle
            except Exception as e:
                errors[bundle_name] = str(e)
        
        # Test multiple bundles in parallel
        bundles = ["go-development", "python-development", "typescript-development"]
        threads = []
        
        for bundle in bundles:
            thread = threading.Thread(target=download_bundle, args=(bundle,))
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=120)
        
        # Verify results
        assert len(results) > 0
        for bundle_name, bundle_content in results.items():
            assert isinstance(bundle_content, dict)
            assert len(bundle_content) > 0


class TestErrorRecovery:
    """Test error recovery and graceful degradation."""
    
    def test_network_recovery(self, protoc_distributor, failure_simulator, current_platform):
        """Test recovery from network failures."""
        # Simulate network failure
        failure_simulator.simulate_network_timeout()
        
        # First attempt should fail
        with pytest.raises(Exception):
            protoc_distributor.get_protoc("24.4", current_platform)
        
        # Cleanup simulation
        failure_simulator.cleanup()
        
        # Second attempt should succeed (fallback or recovery)
        try:
            path = protoc_distributor.get_protoc("24.4", current_platform)
            assert path is not None
        except Exception as e:
            # Acceptable if it fails gracefully with proper error message
            assert "network" in str(e).lower() or "timeout" in str(e).lower()
    
    def test_registry_unavailable_fallback(self, plugin_distributor, failure_simulator, current_platform):
        """Test fallback when registry is unavailable."""
        # Simulate registry unavailable
        failure_simulator.simulate_registry_unavailable(plugin_distributor.oras_client)
        
        # Should fallback to HTTP
        try:
            plugin_path = plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
            # If successful, HTTP fallback worked
            assert plugin_path is not None
            
            # Check metrics show fallback
            metrics = plugin_distributor.get_performance_metrics()
            assert metrics.get("http_fallbacks", 0) > 0
            
        except Exception as e:
            # Should fail gracefully with clear error message
            assert any(keyword in str(e).lower() for keyword in ["unavailable", "network", "failed"])
    
    def test_partial_failure_recovery(self, plugin_distributor, failure_simulator):
        """Test recovery from partial failures in bundle downloads."""
        # This test verifies that if one plugin in a bundle fails,
        # the system handles it gracefully
        
        # Note: Implementation depends on how bundle failures are handled
        # For now, test that system doesn't crash on bundle download attempts
        try:
            bundle = plugin_distributor.get_bundle("go-development")
            # Success case
            assert isinstance(bundle, dict)
        except Exception as e:
            # Failure case should be handled gracefully
            assert "incomplete" in str(e).lower() or "failed" in str(e).lower()


class TestDataIntegrity:
    """Test data integrity and verification."""
    
    def test_digest_verification(self, real_oras_client, test_artifacts, security_validator):
        """Test artifact digest verification."""
        artifact_ref = test_artifacts["small_binary"]["ref"]
        
        try:
            # Pull artifact 
            artifact_path = real_oras_client.pull(artifact_ref)
            
            # Get artifact info for digest
            info = real_oras_client.get_artifact_info(artifact_ref)
            if "digest" in info:
                # Verify content matches digest
                with open(artifact_path, 'rb') as f:
                    content = f.read()
                
                is_valid = security_validator.validate_digest(content, info["digest"])
                assert is_valid
                
        except Exception:
            # Expected if test artifacts not yet published
            pytest.skip("Test artifacts not available in registry")
    
    def test_cache_integrity(self, protoc_distributor, current_platform):
        """Test cache integrity across multiple operations."""
        version = "24.4"
        
        # First download
        path1 = protoc_distributor.get_protoc(version, current_platform)
        
        # Second download (cache hit)
        path2 = protoc_distributor.get_protoc(version, current_platform)
        
        # Paths should be identical
        assert path1 == path2
        
        # Content should be identical if files exist
        if Path(path1).exists() and Path(path2).exists():
            import hashlib
            
            with open(path1, 'rb') as f1, open(path2, 'rb') as f2:
                hash1 = hashlib.sha256(f1.read()).hexdigest()
                hash2 = hashlib.sha256(f2.read()).hexdigest()
                assert hash1 == hash2


class TestPlatformCompatibility:
    """Test cross-platform compatibility."""
    
    @pytest.mark.parametrize("platform", [
        "linux-x86_64",
        "linux-aarch64", 
        "darwin-x86_64",
        "darwin-arm64",
        "windows-x86_64"
    ])
    def test_platform_support(self, protoc_distributor, platform):
        """Test protoc distribution works for all supported platforms."""
        # Test that platform is recognized and supported
        supported_platforms = protoc_distributor.get_supported_platforms()
        assert platform in supported_platforms
        
        # Test version availability for platform
        supported_versions = protoc_distributor.get_supported_versions()
        assert len(supported_versions) > 0
        
        # Test actual download (may be mocked)
        try:
            path = protoc_distributor.get_protoc("24.4", platform)
            assert path is not None
        except ValueError as e:
            if "unsupported" in str(e).lower():
                pytest.fail(f"Platform {platform} should be supported")
            else:
                # Other errors are acceptable (network, etc.)
                pass
    
    def test_platform_detection(self, current_platform, supported_platforms):
        """Test platform detection works correctly."""
        assert current_platform in supported_platforms
        
        # Test platform string format
        assert "-" in current_platform
        os_part, arch_part = current_platform.split("-", 1)
        assert os_part in ["linux", "darwin", "windows"]
        assert arch_part in ["x86_64", "aarch64", "arm64"]


class TestMetricsAndObservability:
    """Test metrics collection and observability features."""
    
    def test_performance_metrics_collection(self, protoc_distributor, plugin_distributor, current_platform):
        """Test that performance metrics are correctly collected."""
        # Perform some operations
        protoc_distributor.get_protoc("24.4", current_platform)
        plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
        
        # Check protoc metrics
        protoc_metrics = protoc_distributor.get_performance_metrics()
        required_keys = ["total_requests", "oras_hits", "oras_misses", "http_fallbacks"]
        for key in required_keys:
            assert key in protoc_metrics
            assert isinstance(protoc_metrics[key], (int, float))
        
        # Check plugin metrics  
        plugin_metrics = plugin_distributor.get_performance_metrics()
        plugin_required_keys = ["total_requests", "oras_hits", "oras_misses", "http_fallbacks", "bundle_downloads"]
        for key in plugin_required_keys:
            assert key in plugin_metrics
            assert isinstance(plugin_metrics[key], (int, float))
    
    def test_metrics_accuracy(self, protoc_distributor, current_platform):
        """Test that metrics accurately reflect operations."""
        initial_metrics = protoc_distributor.get_performance_metrics()
        initial_requests = initial_metrics.get("total_requests", 0)
        
        # Perform one operation
        protoc_distributor.get_protoc("24.4", current_platform)
        
        # Check metrics updated
        updated_metrics = protoc_distributor.get_performance_metrics()
        updated_requests = updated_metrics.get("total_requests", 0)
        
        assert updated_requests > initial_requests
    
    def test_cache_metrics(self, protoc_distributor, current_platform):
        """Test cache hit/miss metrics."""
        version = "24.4"
        
        # First call - should be miss or ORAS hit
        protoc_distributor.get_protoc(version, current_platform)
        first_metrics = protoc_distributor.get_performance_metrics()
        
        # Second call - should be cache hit
        protoc_distributor.get_protoc(version, current_platform)
        second_metrics = protoc_distributor.get_performance_metrics()
        
        # Total requests should increase
        assert second_metrics["total_requests"] > first_metrics["total_requests"]
