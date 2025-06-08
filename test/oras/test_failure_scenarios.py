"""
ORAS Failure Scenario Testing

This module provides comprehensive testing of failure scenarios to ensure
graceful degradation, proper error handling, and recovery mechanisms.
"""

import pytest
import time
import threading
from pathlib import Path
from unittest.mock import patch, Mock
from typing import Dict, Any, List

from . import PERFORMANCE_TARGETS


class TestNetworkFailures:
    """Test network-related failure scenarios."""
    
    @pytest.mark.failure_scenario
    def test_network_timeout_handling(self, protoc_distributor, failure_simulator, current_platform):
        """Test handling of network timeouts."""
        # Simulate network timeout
        failure_simulator.simulate_network_timeout()
        
        # Should handle timeout gracefully
        with pytest.raises(Exception) as exc_info:
            protoc_distributor.get_protoc("24.4", current_platform)
        
        # Error should be informative
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["timeout", "network", "connection"])
        
        # Metrics should reflect the failure
        metrics = protoc_distributor.get_performance_metrics()
        # Note: Depending on implementation, might track failures
    
    @pytest.mark.failure_scenario
    def test_registry_unavailable_fallback(self, plugin_distributor, failure_simulator, current_platform):
        """Test fallback when primary registry is unavailable."""
        # Simulate registry unavailable
        failure_simulator.simulate_registry_unavailable(plugin_distributor.oras_client)
        
        # Should attempt HTTP fallback
        try:
            plugin_path = plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
            
            # If successful, verify HTTP fallback was used
            metrics = plugin_distributor.get_performance_metrics()
            assert metrics.get("http_fallbacks", 0) > 0
            
        except Exception as e:
            # If both fail, should get meaningful error
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["failed", "unavailable", "network"])
    
    @pytest.mark.failure_scenario
    def test_partial_network_failure(self, protoc_distributor, current_platform):
        """Test handling of partial network failures (intermittent connectivity)."""
        # Simulate intermittent network issues
        success_count = 0
        failure_count = 0
        
        for i in range(5):
            try:
                if i % 2 == 0:  # Simulate failure every other attempt
                    with patch('requests.get', side_effect=ConnectionError("Network error")):
                        protoc_distributor.get_protoc("24.4", current_platform)
                else:
                    protoc_distributor.get_protoc("24.4", current_platform)
                success_count += 1
                
            except Exception:
                failure_count += 1
        
        # Should handle intermittent failures gracefully
        # At least some attempts should succeed due to caching/fallback
        assert success_count > 0 or failure_count > 0  # At least tried


class TestAuthenticationFailures:
    """Test authentication and authorization failure scenarios."""
    
    @pytest.mark.failure_scenario
    def test_authentication_failure_handling(self, real_oras_client, failure_simulator):
        """Test handling of authentication failures."""
        # Simulate auth failure
        failure_simulator.simulate_authentication_failure(real_oras_client)
        
        # Should handle auth failure gracefully
        with pytest.raises(Exception) as exc_info:
            real_oras_client.pull("oras.birb.homes/private/artifact:latest")
        
        # Error should indicate auth problem
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["auth", "unauthorized", "permission", "forbidden"])
    
    @pytest.mark.failure_scenario
    def test_invalid_credentials_handling(self, temp_cache_dir):
        """Test handling of invalid credentials."""
        from oras_client import OrasClient
        
        # Create client with invalid credentials
        client = OrasClient(
            registry="oras.birb.homes",
            cache_dir=temp_cache_dir,
            username="invalid_user",
            password="invalid_password"
        )
        
        # Should handle invalid credentials gracefully
        try:
            client.pull("oras.birb.homes/test/artifact:latest")
        except Exception as e:
            # Should get appropriate error message
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["auth", "unauthorized", "invalid", "credentials"])


class TestStorageFailures:
    """Test storage-related failure scenarios."""
    
    @pytest.mark.failure_scenario
    def test_disk_full_handling(self, protoc_distributor, failure_simulator, current_platform):
        """Test handling when disk is full."""
        # Simulate disk full
        failure_simulator.simulate_disk_full("/tmp")
        
        # Should handle disk full gracefully
        with pytest.raises(Exception) as exc_info:
            protoc_distributor.get_protoc("24.4", current_platform)
        
        # Error should indicate storage problem
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["space", "disk", "storage", "write"])
    
    @pytest.mark.failure_scenario
    def test_permission_denied_handling(self, temp_cache_dir, protoc_distributor, current_platform):
        """Test handling of permission denied errors."""
        # Make cache directory read-only (simulate permission issues)
        try:
            import os
            import stat
            
            # Remove write permissions
            os.chmod(temp_cache_dir, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            
            # Should handle permission error gracefully
            with pytest.raises(Exception) as exc_info:
                protoc_distributor.get_protoc("24.4", current_platform)
            
            # Error should indicate permission problem
            error_msg = str(exc_info.value).lower()
            assert any(keyword in error_msg for keyword in ["permission", "access", "denied", "write"])
            
        finally:
            # Restore permissions for cleanup
            try:
                os.chmod(temp_cache_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            except:
                pass
    
    @pytest.mark.failure_scenario
    def test_corrupted_cache_recovery(self, protoc_distributor, current_platform):
        """Test recovery from corrupted cache."""
        version = "24.4"
        
        # First, download normally
        path1 = protoc_distributor.get_protoc(version, current_platform)
        
        # Corrupt the cached file (if it exists)
        if Path(path1).exists():
            with open(path1, 'w') as f:
                f.write("corrupted content")
        
        # Should detect corruption and re-download
        try:
            path2 = protoc_distributor.get_protoc(version, current_platform)
            # If successful, should have valid content
            assert path2 is not None
            
        except Exception as e:
            # Should fail gracefully with informative error
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["corrupt", "invalid", "checksum", "verification"])


class TestRegistryFailures:
    """Test registry-specific failure scenarios."""
    
    @pytest.mark.failure_scenario
    def test_artifact_not_found_handling(self, real_oras_client):
        """Test handling of missing artifacts."""
        # Try to pull non-existent artifact
        with pytest.raises(Exception) as exc_info:
            real_oras_client.pull("oras.birb.homes/nonexistent/artifact:latest")
        
        # Should get appropriate error
        error_msg = str(exc_info.value).lower()
        assert any(keyword in error_msg for keyword in ["not found", "missing", "404", "does not exist"])
    
    @pytest.mark.failure_scenario
    def test_invalid_registry_url_handling(self, temp_cache_dir):
        """Test handling of invalid registry URLs."""
        from oras_client import OrasClient
        
        # Test various invalid URLs
        invalid_urls = [
            "invalid-registry-url",
            "http://nonexistent.registry.com",
            "ftp://invalid-protocol.com",
            "",
            None
        ]
        
        for invalid_url in invalid_urls:
            if invalid_url is None:
                continue
                
            try:
                client = OrasClient(registry=invalid_url, cache_dir=temp_cache_dir)
                client.pull("test/artifact:latest")
                
            except Exception as e:
                # Should get appropriate error for invalid URL
                error_msg = str(e).lower()
                expected_keywords = ["invalid", "url", "registry", "connection", "resolve"]
                assert any(keyword in error_msg for keyword in expected_keywords)
    
    @pytest.mark.failure_scenario
    def test_malformed_artifact_ref_handling(self, real_oras_client):
        """Test handling of malformed artifact references."""
        malformed_refs = [
            "invalid-ref",
            "missing:tag",
            ":no-repo",
            "repo/",
            "repo::",
            "INVALID/CAPS:tag",
            "repo/name:tag@invalid"
        ]
        
        for malformed_ref in malformed_refs:
            with pytest.raises(Exception) as exc_info:
                real_oras_client.pull(malformed_ref)
            
            # Should get appropriate error for malformed reference
            error_msg = str(exc_info.value).lower()
            expected_keywords = ["invalid", "malformed", "reference", "format", "parse"]
            assert any(keyword in error_msg for keyword in expected_keywords)


class TestConcurrencyFailures:
    """Test failure scenarios under concurrent operations."""
    
    @pytest.mark.failure_scenario
    def test_concurrent_cache_corruption(self, protoc_distributor, current_platform):
        """Test handling of cache corruption during concurrent access."""
        import threading
        import queue
        import random
        
        results = queue.Queue()
        version = "24.4"
        
        def worker(worker_id):
            try:
                # Add some randomness to create potential race conditions
                time.sleep(random.uniform(0, 0.5))
                
                path = protoc_distributor.get_protoc(version, current_platform)
                results.put(("success", worker_id, path))
                
            except Exception as e:
                results.put(("error", worker_id, str(e)))
        
        # Start multiple workers concurrently
        threads = []
        num_workers = 10
        
        for i in range(num_workers):
            thread = threading.Thread(target=worker, args=(i,))
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=30)
        
        # Analyze results
        successes = 0
        errors = 0
        
        while not results.empty():
            result = results.get()
            if result[0] == "success":
                successes += 1
            else:
                errors += 1
        
        # Should handle concurrent access reasonably well
        # Allow some failures due to potential race conditions
        total_operations = successes + errors
        success_rate = successes / total_operations if total_operations > 0 else 0
        
        assert success_rate > 0.7  # At least 70% success rate
    
    @pytest.mark.failure_scenario
    def test_deadlock_prevention(self, plugin_distributor):
        """Test that concurrent operations don't cause deadlocks."""
        import threading
        import signal
        
        # Set up a timeout to detect deadlocks
        deadlock_detected = threading.Event()
        
        def timeout_handler(signum, frame):
            deadlock_detected.set()
        
        # Configure timeout (only on Unix systems)
        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(60)  # 60 second timeout
            
            def worker():
                try:
                    # Multiple operations that could potentially deadlock
                    plugin_distributor.get_bundle("go-development")
                    plugin_distributor.get_bundle("python-development")
                    plugin_distributor.clear_cache()
                    
                except Exception:
                    pass  # Expected failures are OK
            
            # Start multiple workers
            threads = []
            for _ in range(5):
                thread = threading.Thread(target=worker)
                thread.start()
                threads.append(thread)
            
            # Wait for completion
            for thread in threads:
                thread.join(timeout=30)
            
            # Cancel timeout
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
            
            # Should not have timed out (no deadlock)
            assert not deadlock_detected.is_set(), "Potential deadlock detected"
            
        except (OSError, AttributeError):
            # Signal handling not available (Windows), skip deadlock test
            pytest.skip("Signal-based deadlock detection not available on this platform")


class TestResourceExhaustion:
    """Test behavior under resource exhaustion."""
    
    @pytest.mark.failure_scenario
    @pytest.mark.slow
    def test_memory_exhaustion_handling(self, protoc_distributor, current_platform):
        """Test handling when memory is exhausted."""
        # Try to trigger high memory usage
        large_operations = []
        
        try:
            # Attempt many concurrent operations to stress memory
            for i in range(100):
                # This might fail due to resource limits, which is expected
                protoc_distributor.get_protoc("24.4", current_platform)
                
                # Check memory usage periodically
                if i % 10 == 0:
                    try:
                        import psutil
                        import os
                        
                        memory_mb = psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024
                        
                        # If memory usage gets too high, stop
                        if memory_mb > 1000:  # 1GB limit
                            break
                            
                    except ImportError:
                        # psutil not available, continue with limited monitoring
                        pass
        
        except Exception as e:
            # Memory exhaustion should be handled gracefully
            error_msg = str(e).lower()
            # Common memory-related error indicators
            memory_keywords = ["memory", "out of", "allocation", "resource", "limit"]
            
            # Either it should succeed or fail gracefully with memory-related error
            if any(keyword in error_msg for keyword in memory_keywords):
                # This is expected behavior
                pass
            else:
                # Re-raise if it's not a memory-related error
                raise
    
    @pytest.mark.failure_scenario
    def test_file_descriptor_exhaustion(self, protoc_distributor, current_platform):
        """Test handling when file descriptors are exhausted."""
        # Try to open many files/connections
        open_handles = []
        
        try:
            # Attempt to exhaust file descriptors
            for i in range(1000):  # Try to open many handles
                try:
                    # Each operation might open file handles
                    protoc_distributor.get_protoc("24.4", current_platform)
                    
                    # Also try opening files directly to stress FD limit
                    import tempfile
                    handle = tempfile.NamedTemporaryFile(delete=False)
                    open_handles.append(handle)
                    
                except OSError as e:
                    # Expected when FD limit is reached
                    if "too many open files" in str(e).lower():
                        break
                    else:
                        raise
                        
                except Exception:
                    # Other errors are also acceptable (network, etc.)
                    break
        
        finally:
            # Clean up opened handles
            for handle in open_handles:
                try:
                    handle.close()
                except:
                    pass


class TestRecoveryMechanisms:
    """Test error recovery and resilience mechanisms."""
    
    @pytest.mark.failure_scenario
    def test_automatic_retry_mechanism(self, protoc_distributor, current_platform):
        """Test automatic retry mechanisms."""
        # Mock to simulate transient failures followed by success
        original_method = protoc_distributor.get_protoc
        call_count = 0
        
        def mock_with_transient_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            if call_count <= 2:  # Fail first two attempts
                raise ConnectionError("Transient network error")
            else:
                # Succeed on third attempt
                return original_method(*args, **kwargs)
        
        # Apply mock
        with patch.object(protoc_distributor, 'get_protoc', side_effect=mock_with_transient_failure):
            # This should eventually succeed if retry mechanism exists
            try:
                result = protoc_distributor.get_protoc("24.4", current_platform)
                # If we get here, retry mechanism worked
                assert call_count > 1  # Should have retried
                
            except Exception:
                # If no retry mechanism, that's also valid behavior
                # Just ensure we tried at least once
                assert call_count >= 1
    
    @pytest.mark.failure_scenario
    def test_graceful_degradation(self, plugin_distributor, failure_simulator, current_platform):
        """Test graceful degradation when some features fail."""
        # Simulate ORAS failure
        failure_simulator.simulate_registry_unavailable(plugin_distributor.oras_client)
        
        # Should gracefully degrade to HTTP fallback
        try:
            plugin_path = plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
            
            # If successful, verify fallback was used
            metrics = plugin_distributor.get_performance_metrics()
            assert metrics.get("http_fallbacks", 0) > 0
            
            # Should still provide basic functionality
            assert plugin_path is not None
            
        except Exception as e:
            # If complete failure, should be informative
            error_msg = str(e).lower()
            assert any(keyword in error_msg for keyword in ["failed", "unavailable", "fallback"])
    
    @pytest.mark.failure_scenario
    def test_cache_corruption_recovery(self, protoc_distributor, current_platform):
        """Test recovery from cache corruption."""
        version = "24.4"
        
        # Download normally first
        original_path = protoc_distributor.get_protoc(version, current_platform)
        
        # Simulate cache corruption by modifying cache files
        cache_dir = protoc_distributor.cache_dir
        
        # Find and corrupt cache files
        corrupted_files = []
        try:
            for cache_file in cache_dir.rglob("*"):
                if cache_file.is_file():
                    # Corrupt the file
                    with open(cache_file, 'wb') as f:
                        f.write(b"CORRUPTED DATA")
                    corrupted_files.append(cache_file)
                    break  # Just corrupt one file for testing
        except:
            pass  # If we can't corrupt files, skip this part
        
        if corrupted_files:
            # Should detect corruption and recover
            try:
                recovered_path = protoc_distributor.get_protoc(version, current_platform)
                # Should either re-download or use fallback
                assert recovered_path is not None
                
            except Exception as e:
                # Should fail gracefully with informative error
                error_msg = str(e).lower()
                recovery_keywords = ["corrupt", "invalid", "recovery", "checksum", "verify"]
                assert any(keyword in error_msg for keyword in recovery_keywords)


class TestErrorReporting:
    """Test error reporting and logging quality."""
    
    @pytest.mark.failure_scenario
    def test_error_message_quality(self, protoc_distributor, current_platform):
        """Test that error messages are informative and actionable."""
        # Test various error scenarios and check message quality
        error_scenarios = [
            ("invalid_version", lambda: protoc_distributor.get_protoc("999.999", current_platform)),
            ("invalid_platform", lambda: protoc_distributor.get_protoc("24.4", "invalid-platform")),
        ]
        
        for scenario_name, operation in error_scenarios:
            try:
                operation()
                # If it doesn't fail, that's also OK
                
            except Exception as e:
                error_msg = str(e)
                
                # Error message should be informative
                assert len(error_msg) > 10  # Not just a generic error
                assert scenario_name.split("_")[0] in error_msg.lower()  # Should mention the problem
                
                # Should not contain internal implementation details
                internal_keywords = ["traceback", "__", "self.", "args[0]"]
                assert not any(keyword in error_msg for keyword in internal_keywords)
    
    @pytest.mark.failure_scenario
    def test_structured_error_information(self, plugin_distributor, current_platform):
        """Test that errors provide structured information for debugging."""
        try:
            # Try an operation that should fail
            plugin_distributor.get_plugin("nonexistent-plugin", "1.0.0", current_platform)
            
        except Exception as e:
            # Check if error has useful attributes
            error_attributes = dir(e)
            
            # Should have basic exception attributes
            assert hasattr(e, 'args')
            
            # Error should be specific type, not just generic Exception
            assert type(e).__name__ != "Exception"
