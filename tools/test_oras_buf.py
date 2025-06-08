#!/usr/bin/env python3
"""
Comprehensive test suite for ORAS-based Buf CLI distribution.

This module tests the BufOrasDistributor across multiple platforms,
versions, and scenarios to ensure reliable Buf CLI distribution.
"""

import os
import pytest
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from oras_buf import BufOrasDistributor, detect_platform_string
from oras_client import OrasClientError, ArtifactNotFoundError, RegistryAuthError


class TestBufOrasDistributor(unittest.TestCase):
    """Test cases for BufOrasDistributor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.test_registry = "test.registry.local"
        self.verbose = True
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_initialization_with_oras_available(self):
        """Test successful initialization with ORAS client available."""
        with patch('oras_buf.OrasClient') as mock_oras:
            mock_oras.return_value = MagicMock()
            
            distributor = BufOrasDistributor(
                registry=self.test_registry,
                cache_dir=str(self.cache_dir),
                verbose=self.verbose
            )
            
            self.assertEqual(distributor.registry, self.test_registry)
            self.assertTrue(distributor.oras_available)
            self.assertTrue(self.cache_dir.exists())
            mock_oras.assert_called_once()
    
    def test_initialization_with_oras_unavailable(self):
        """Test initialization when ORAS client is unavailable."""
        with patch('oras_buf.OrasClient') as mock_oras:
            mock_oras.side_effect = Exception("ORAS not available")
            
            distributor = BufOrasDistributor(
                registry=self.test_registry,
                cache_dir=str(self.cache_dir),
                verbose=self.verbose
            )
            
            self.assertFalse(distributor.oras_available)
            self.assertIsNotNone(distributor.http_fallback)
    
    def test_get_supported_versions(self):
        """Test getting list of supported Buf CLI versions."""
        distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
        versions = distributor.get_supported_versions()
        
        self.assertIsInstance(versions, list)
        self.assertIn("1.47.2", versions)
        self.assertIn("1.46.1", versions)
        self.assertIn("1.45.0", versions)
    
    def test_get_supported_platforms(self):
        """Test getting list of supported platforms."""
        distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
        platforms = distributor.get_supported_platforms()
        
        self.assertIsInstance(platforms, list)
        expected_platforms = [
            "darwin-arm64", "darwin-x86_64", 
            "linux-aarch64", "linux-x86_64", 
            "windows-x86_64"
        ]
        for platform in expected_platforms:
            self.assertIn(platform, platforms)
    
    def test_get_buf_with_oras_success(self):
        """Test successful Buf CLI retrieval via ORAS."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.pull.return_value = Path("/fake/cache/buf")
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            result = distributor.get_buf("1.47.2", "linux-x86_64")
            
            self.assertEqual(result, "/fake/cache/buf")
            mock_oras.pull.assert_called_once()
            self.assertEqual(distributor.metrics["oras_hits"], 1)
            self.assertEqual(distributor.metrics["http_fallbacks"], 0)
    
    def test_get_buf_with_oras_failure_http_fallback(self):
        """Test HTTP fallback when ORAS fails."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.pull.side_effect = ArtifactNotFoundError("Artifact not found")
            mock_oras_class.return_value = mock_oras
            
            with patch('oras_buf.BufDownloader') as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.download_buf.return_value = Path("/fake/http/buf")
                mock_downloader_class.return_value = mock_downloader
                
                distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
                
                result = distributor.get_buf("1.47.2", "linux-x86_64")
                
                self.assertEqual(result, "/fake/http/buf")
                self.assertEqual(distributor.metrics["oras_misses"], 1)
                self.assertEqual(distributor.metrics["http_fallbacks"], 1)
    
    def test_get_buf_with_unsupported_version(self):
        """Test error handling for unsupported version."""
        distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
        
        with self.assertRaises(ValueError) as context:
            distributor.get_buf("999.999.999", "linux-x86_64")
        
        self.assertIn("Unsupported Buf CLI version", str(context.exception))
    
    def test_get_buf_with_unsupported_platform(self):
        """Test error handling for unsupported platform."""
        distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
        
        with self.assertRaises(ValueError) as context:
            distributor.get_buf("1.47.2", "unsupported-platform")
        
        self.assertIn("Unsupported platform", str(context.exception))
    
    def test_get_buf_with_platform_autodetection(self):
        """Test automatic platform detection."""
        with patch('oras_buf.detect_platform_string') as mock_detect:
            mock_detect.return_value = "linux-x86_64"
            
            with patch('oras_buf.OrasClient') as mock_oras_class:
                mock_oras = MagicMock()
                mock_oras.pull.return_value = Path("/fake/cache/buf")
                mock_oras_class.return_value = mock_oras
                
                distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
                
                result = distributor.get_buf("1.47.2")  # No platform specified
                
                mock_detect.assert_called_once()
                self.assertEqual(result, "/fake/cache/buf")
    
    def test_get_buf_with_both_oras_and_http_failure(self):
        """Test error handling when both ORAS and HTTP fail."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.pull.side_effect = ArtifactNotFoundError("ORAS failed")
            mock_oras_class.return_value = mock_oras
            
            with patch('oras_buf.BufDownloader') as mock_downloader_class:
                mock_downloader = MagicMock()
                mock_downloader.download_buf.side_effect = Exception("HTTP failed")
                mock_downloader_class.return_value = mock_downloader
                
                distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
                
                with self.assertRaises(RuntimeError) as context:
                    distributor.get_buf("1.47.2", "linux-x86_64")
                
                self.assertIn("Both ORAS and HTTP failed", str(context.exception))
    
    def test_performance_metrics_tracking(self):
        """Test performance metrics collection."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.pull.return_value = Path("/fake/cache/buf")
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            # Make multiple requests
            distributor.get_buf("1.47.2", "linux-x86_64")
            distributor.get_buf("1.46.1", "linux-x86_64")
            
            metrics = distributor.get_performance_metrics()
            
            self.assertEqual(metrics["total_requests"], 2)
            self.assertEqual(metrics["oras_hits"], 2)
            self.assertEqual(metrics["oras_hit_rate"], 1.0)
            self.assertEqual(metrics["http_fallback_rate"], 0.0)
            self.assertGreaterEqual(metrics["avg_oras_time"], 0.0)
    
    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.clear_cache.return_value = 5
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            # Create some test cache files
            http_cache_dir = distributor.cache_dir / "http_buf"
            http_cache_dir.mkdir(parents=True, exist_ok=True)
            test_file = http_cache_dir / "test_buf"
            test_file.write_text("test content")
            
            results = distributor.clear_cache()
            
            self.assertEqual(results["oras_cleared"], 5)
            self.assertEqual(results["http_cleared"], 1)
            mock_oras.clear_cache.assert_called_once()
    
    def test_cache_clearing_with_age_filter(self):
        """Test cache clearing with age-based filtering."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.clear_cache.return_value = 3
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            results = distributor.clear_cache(older_than_days=7)
            
            self.assertEqual(results["oras_cleared"], 3)
            mock_oras.clear_cache.assert_called_with(7)


class TestPlatformDetection(unittest.TestCase):
    """Test cases for platform detection functionality."""
    
    def test_detect_platform_string_linux_x86_64(self):
        """Test platform detection for Linux x86_64."""
        with patch('platform.system') as mock_system, \
             patch('platform.machine') as mock_machine:
            
            mock_system.return_value = "Linux"
            mock_machine.return_value = "x86_64"
            
            result = detect_platform_string()
            self.assertEqual(result, "linux-x86_64")
    
    def test_detect_platform_string_darwin_arm64(self):
        """Test platform detection for macOS ARM64."""
        with patch('platform.system') as mock_system, \
             patch('platform.machine') as mock_machine:
            
            mock_system.return_value = "Darwin"
            mock_machine.return_value = "arm64"
            
            result = detect_platform_string()
            self.assertEqual(result, "darwin-arm64")
    
    def test_detect_platform_string_windows_x86_64(self):
        """Test platform detection for Windows x86_64."""
        with patch('platform.system') as mock_system, \
             patch('platform.machine') as mock_machine:
            
            mock_system.return_value = "Windows"
            mock_machine.return_value = "AMD64"
            
            result = detect_platform_string()
            self.assertEqual(result, "windows-x86_64")
    
    def test_detect_platform_string_unsupported_os(self):
        """Test error handling for unsupported operating system."""
        with patch('platform.system') as mock_system, \
             patch('platform.machine') as mock_machine:
            
            mock_system.return_value = "UnsupportedOS"
            mock_machine.return_value = "x86_64"
            
            with self.assertRaises(ValueError) as context:
                detect_platform_string()
            
            self.assertIn("Unsupported operating system", str(context.exception))
    
    def test_detect_platform_string_unsupported_arch(self):
        """Test error handling for unsupported architecture."""
        with patch('platform.system') as mock_system, \
             patch('platform.machine') as mock_machine:
            
            mock_system.return_value = "Linux"
            mock_machine.return_value = "unsupported_arch"
            
            with self.assertRaises(ValueError) as context:
                detect_platform_string()
            
            self.assertIn("Unsupported architecture", str(context.exception))


class TestBufOrasDistributorIntegration(unittest.TestCase):
    """Integration tests for BufOrasDistributor."""
    
    def setUp(self):
        """Set up integration test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "integration_cache"
        self.test_registry = "localhost:5000"  # For localhost testing
    
    def tearDown(self):
        """Clean up integration test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    @unittest.skipUnless(
        os.environ.get("RUN_INTEGRATION_TESTS", "false").lower() == "true",
        "Integration tests require RUN_INTEGRATION_TESTS=true"
    )
    def test_integration_with_localhost_registry(self):
        """Test integration with localhost ORAS registry."""
        # This test requires a running localhost registry
        distributor = BufOrasDistributor(
            registry=self.test_registry,
            cache_dir=str(self.cache_dir),
            verbose=True
        )
        
        # If ORAS is not available, this should fall back to HTTP
        try:
            result = distributor.get_buf("1.47.2", "linux-x86_64")
            self.assertIsInstance(result, str)
            self.assertTrue(Path(result).exists())
        except RuntimeError as e:
            # Expected if both ORAS and HTTP fail in test environment
            self.assertIn("Both ORAS and HTTP failed", str(e))
    
    def test_artifact_configuration_completeness(self):
        """Test that all configured artifacts have required fields."""
        distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
        
        required_fields = [
            "oras_ref", "digest", "fallback_url", 
            "fallback_sha256", "binary_path"
        ]
        
        for version, platforms in distributor.buf_artifacts.items():
            for platform, config in platforms.items():
                for field in required_fields:
                    self.assertIn(field, config, 
                        f"Missing {field} in {version}/{platform}")
                
                # Validate ORAS ref format
                self.assertTrue(config["oras_ref"].startswith(distributor.registry))
                self.assertIn(version, config["oras_ref"])
                
                # Validate digest format
                self.assertTrue(config["digest"].startswith("sha256:"))
                self.assertEqual(len(config["digest"]), 71)  # sha256: + 64 hex chars
                
                # Validate URL format
                self.assertTrue(config["fallback_url"].startswith("https://"))
                self.assertIn("github.com/bufbuild/buf", config["fallback_url"])


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests for Buf CLI distribution."""
    
    def setUp(self):
        """Set up performance test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "perf_cache"
    
    def tearDown(self):
        """Clean up performance test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_oras_performance_benchmark(self):
        """Benchmark ORAS distribution performance."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            
            # Simulate realistic ORAS timing
            def mock_pull(*args, **kwargs):
                time.sleep(0.1)  # Simulate 100ms ORAS operation
                return Path("/fake/cache/buf")
            
            mock_oras.pull.side_effect = mock_pull
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            start_time = time.time()
            result = distributor.get_buf("1.47.2", "linux-x86_64")
            elapsed_time = time.time() - start_time
            
            # Should complete within reasonable time
            self.assertLess(elapsed_time, 1.0)  # Less than 1 second
            
            metrics = distributor.get_performance_metrics()
            self.assertGreater(metrics["avg_oras_time"], 0.0)
            self.assertLess(metrics["avg_oras_time"], 0.5)  # Less than 500ms
    
    def test_multiple_requests_performance(self):
        """Test performance of multiple concurrent-style requests."""
        with patch('oras_buf.OrasClient') as mock_oras_class:
            mock_oras = MagicMock()
            mock_oras.pull.return_value = Path("/fake/cache/buf")
            mock_oras_class.return_value = mock_oras
            
            distributor = BufOrasDistributor(cache_dir=str(self.cache_dir))
            
            # Make multiple requests for different platforms
            platforms = ["linux-x86_64", "linux-aarch64", "darwin-arm64"]
            start_time = time.time()
            
            for platform in platforms:
                result = distributor.get_buf("1.47.2", platform)
                self.assertIsInstance(result, str)
            
            elapsed_time = time.time() - start_time
            
            # All requests should complete quickly
            self.assertLess(elapsed_time, 2.0)  # Less than 2 seconds total
            
            metrics = distributor.get_performance_metrics()
            self.assertEqual(metrics["total_requests"], 3)
            self.assertEqual(metrics["oras_hits"], 3)


def run_comprehensive_tests():
    """Run the comprehensive test suite."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestBufOrasDistributor,
        TestPlatformDetection,
        TestBufOrasDistributorIntegration,
        TestPerformanceBenchmarks,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    
    # Check if we should run integration tests
    if len(sys.argv) > 1 and sys.argv[1] == "--integration":
        os.environ["RUN_INTEGRATION_TESTS"] = "true"
    
    # Run tests
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)
