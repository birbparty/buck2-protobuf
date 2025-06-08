#!/usr/bin/env python3
"""
Comprehensive tests for ORAS plugin distribution system.

This test suite validates the ORAS plugin distributor functionality including
ORAS/HTTP fallback, plugin bundles, caching, and performance metrics.
"""

import json
import os
import pytest
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
from oras_plugins import PluginOrasDistributor, detect_platform_string
from oras_client import OrasClientError, ArtifactNotFoundError


class TestPluginOrasDistributor(unittest.TestCase):
    """Test cases for PluginOrasDistributor."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.registry = "test.registry.local"
        
        # Create distributor with mocked dependencies
        with patch('oras_plugins.OrasClient') as mock_oras_client, \
             patch('oras_plugins.PluginDownloader') as mock_plugin_downloader:
            
            self.mock_oras_client = Mock()
            self.mock_plugin_downloader = Mock()
            
            mock_oras_client.return_value = self.mock_oras_client
            mock_plugin_downloader.return_value = self.mock_plugin_downloader
            
            self.distributor = PluginOrasDistributor(
                registry=self.registry,
                cache_dir=str(self.cache_dir),
                verbose=True
            )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_initialization(self):
        """Test distributor initialization."""
        self.assertEqual(self.distributor.registry, self.registry)
        self.assertEqual(self.distributor.cache_dir, self.cache_dir)
        self.assertTrue(self.distributor.oras_available)
        self.assertIn("protoc-gen-go", self.distributor.plugin_artifacts)
        self.assertIn("go-development", self.distributor.plugin_bundles)
    
    def test_get_supported_plugins(self):
        """Test getting supported plugins."""
        plugins = self.distributor.get_supported_plugins()
        
        self.assertIn("protoc-gen-go", plugins)
        self.assertIn("protoc-gen-go-grpc", plugins)
        self.assertIn("grpcio-tools", plugins)
        self.assertIn("protoc-gen-ts", plugins)
    
    def test_get_supported_versions(self):
        """Test getting supported versions for plugins."""
        go_versions = self.distributor.get_supported_versions("protoc-gen-go")
        self.assertIn("1.34.2", go_versions)
        
        grpc_versions = self.distributor.get_supported_versions("protoc-gen-go-grpc")
        self.assertIn("1.5.1", grpc_versions)
        
        # Test unsupported plugin
        unknown_versions = self.distributor.get_supported_versions("unknown-plugin")
        self.assertEqual(unknown_versions, [])
    
    def test_get_supported_platforms(self):
        """Test getting supported platforms."""
        platforms = self.distributor.get_supported_platforms()
        
        expected_platforms = [
            "darwin-arm64", "darwin-x86_64", "linux-aarch64", 
            "linux-x86_64", "windows-x86_64"
        ]
        
        for platform in expected_platforms:
            self.assertIn(platform, platforms)
    
    def test_get_supported_bundles(self):
        """Test getting supported bundles."""
        bundles = self.distributor.get_supported_bundles()
        
        self.assertIn("go-development", bundles)
        self.assertIn("python-development", bundles)
        self.assertIn("typescript-development", bundles)
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_plugin_binary_oras_success(self, mock_detect_platform):
        """Test successful binary plugin download via ORAS."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Mock successful ORAS pull
        mock_binary_path = Path(self.temp_dir) / "protoc-gen-go"
        mock_binary_path.touch()
        self.mock_oras_client.pull.return_value = mock_binary_path
        
        result = self.distributor.get_plugin("protoc-gen-go", "1.34.2")
        
        self.assertEqual(result, str(mock_binary_path))
        self.mock_oras_client.pull.assert_called_once()
        self.assertEqual(self.distributor.metrics["oras_hits"], 1)
        self.assertEqual(self.distributor.metrics["total_requests"], 1)
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_plugin_binary_http_fallback(self, mock_detect_platform):
        """Test binary plugin HTTP fallback when ORAS fails."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Mock ORAS failure
        self.mock_oras_client.pull.side_effect = ArtifactNotFoundError("Not found")
        
        # Mock HTTP success
        mock_binary_path = "/path/to/protoc-gen-go"
        self.mock_plugin_downloader.download_plugin.return_value = mock_binary_path
        
        result = self.distributor.get_plugin("protoc-gen-go", "1.34.2")
        
        self.assertEqual(result, mock_binary_path)
        self.mock_oras_client.pull.assert_called_once()
        self.mock_plugin_downloader.download_plugin.assert_called_once_with(
            "protoc-gen-go", "1.34.2", "linux-x86_64"
        )
        self.assertEqual(self.distributor.metrics["oras_misses"], 1)
        self.assertEqual(self.distributor.metrics["http_fallbacks"], 1)
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_plugin_python_package(self, mock_detect_platform):
        """Test Python package plugin installation."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Mock ORAS failure for Python package
        self.mock_oras_client.pull.side_effect = ArtifactNotFoundError("Not found")
        
        # Mock HTTP Python package installation
        mock_wrapper_path = Path(self.temp_dir) / "grpc_tools.protoc"
        self.mock_plugin_downloader.install_python_package.return_value = True
        self.mock_plugin_downloader.create_python_wrapper.return_value = mock_wrapper_path
        
        result = self.distributor.get_plugin("grpcio-tools", "1.66.2")
        
        self.assertEqual(result, str(mock_wrapper_path))
        self.mock_plugin_downloader.install_python_package.assert_called_once()
        self.mock_plugin_downloader.create_python_wrapper.assert_called_once()
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_plugin_unsupported(self, mock_detect_platform):
        """Test handling of unsupported plugin/version/platform."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Test unsupported plugin
        with self.assertRaises(ValueError) as ctx:
            self.distributor.get_plugin("unknown-plugin", "1.0.0")
        self.assertIn("Unsupported plugin", str(ctx.exception))
        
        # Test unsupported version
        with self.assertRaises(ValueError) as ctx:
            self.distributor.get_plugin("protoc-gen-go", "999.0.0")
        self.assertIn("Unsupported version", str(ctx.exception))
        
        # Test unsupported platform
        with self.assertRaises(ValueError) as ctx:
            self.distributor.get_plugin("protoc-gen-go", "1.34.2", "unsupported-platform")
        self.assertIn("Unsupported platform", str(ctx.exception))
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_bundle_success(self, mock_detect_platform):
        """Test successful bundle download."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Mock individual plugin downloads
        with patch.object(self.distributor, 'get_plugin') as mock_get_plugin:
            mock_get_plugin.side_effect = [
                "/path/to/protoc-gen-go",
                "/path/to/protoc-gen-go-grpc"
            ]
            
            result = self.distributor.get_bundle("go-development")
            
            expected = {
                "protoc-gen-go": "/path/to/protoc-gen-go",
                "protoc-gen-go-grpc": "/path/to/protoc-gen-go-grpc"
            }
            
            self.assertEqual(result, expected)
            self.assertEqual(mock_get_plugin.call_count, 2)
            self.assertEqual(self.distributor.metrics["bundle_downloads"], 1)
    
    @patch('oras_plugins.detect_platform_string')
    def test_get_bundle_partial_failure(self, mock_detect_platform):
        """Test bundle download with partial plugin failure."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        # Mock plugin downloads with one failure
        with patch.object(self.distributor, 'get_plugin') as mock_get_plugin:
            mock_get_plugin.side_effect = [
                "/path/to/protoc-gen-go",
                RuntimeError("Plugin download failed")
            ]
            
            with self.assertRaises(RuntimeError) as ctx:
                self.distributor.get_bundle("go-development")
            
            self.assertIn("Bundle go-development incomplete", str(ctx.exception))
    
    def test_get_bundle_unsupported(self):
        """Test handling of unsupported bundles."""
        with self.assertRaises(ValueError) as ctx:
            self.distributor.get_bundle("unknown-bundle")
        self.assertIn("Unsupported bundle", str(ctx.exception))
        
        with self.assertRaises(ValueError) as ctx:
            self.distributor.get_bundle("go-development", "unknown-version")
        self.assertIn("Unsupported version", str(ctx.exception))
    
    def test_performance_metrics(self):
        """Test performance metrics calculation."""
        # Simulate some operations
        self.distributor.metrics["total_requests"] = 10
        self.distributor.metrics["oras_hits"] = 7
        self.distributor.metrics["http_fallbacks"] = 2
        self.distributor.metrics["cache_hits"] = 1
        
        metrics = self.distributor.get_performance_metrics()
        
        self.assertEqual(metrics["oras_hit_rate"], 0.7)
        self.assertEqual(metrics["http_fallback_rate"], 0.2)
        self.assertEqual(metrics["cache_hit_rate"], 0.1)
    
    def test_clear_cache(self):
        """Test cache clearing functionality."""
        # Create some test cache files
        oras_cache = self.cache_dir / "oras"
        oras_cache.mkdir(parents=True, exist_ok=True)
        (oras_cache / "test_file").write_text("test")
        
        http_cache = self.cache_dir / "http"
        http_cache.mkdir(parents=True, exist_ok=True)
        (http_cache / "test_file").write_text("test")
        
        plugin_cache = self.cache_dir / "plugin-cache"
        plugin_cache.mkdir(parents=True, exist_ok=True)
        (plugin_cache / "test_file").write_text("test")
        
        # Mock ORAS client clear_cache
        self.mock_oras_client.clear_cache.return_value = 5
        
        result = self.distributor.clear_cache()
        
        self.assertIn("oras_cleared", result)
        self.assertIn("http_cleared", result)
        self.assertIn("plugin_cleared", result)
        self.mock_oras_client.clear_cache.assert_called_once()


class TestIntegration(unittest.TestCase):
    """Integration tests that require network access."""
    
    @pytest.mark.integration
    def test_platform_detection(self):
        """Test platform detection functionality."""
        platform = detect_platform_string()
        
        # Should return a valid platform string
        valid_platforms = [
            "linux-x86_64", "linux-aarch64",
            "darwin-x86_64", "darwin-arm64",
            "windows-x86_64"
        ]
        
        self.assertIn(platform, valid_platforms)
    
    @pytest.mark.integration
    def test_distributor_initialization_real(self):
        """Test real distributor initialization without mocks."""
        with tempfile.TemporaryDirectory() as temp_dir:
            distributor = PluginOrasDistributor(
                registry="oras.birb.homes",
                cache_dir=temp_dir,
                verbose=False
            )
            
            # Should initialize successfully
            self.assertIsNotNone(distributor)
            self.assertTrue(len(distributor.get_supported_plugins()) > 0)
            self.assertTrue(len(distributor.get_supported_bundles()) > 0)


class TestPluginBundles(unittest.TestCase):
    """Test plugin bundle functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        
        with patch('oras_plugins.OrasClient'), patch('oras_plugins.PluginDownloader'):
            self.distributor = PluginOrasDistributor(
                registry="test.registry.local",
                cache_dir=str(self.cache_dir),
                verbose=False
            )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_bundle_configuration(self):
        """Test bundle configuration structure."""
        bundles = self.distributor.plugin_bundles
        
        # Test go-development bundle
        go_bundle = bundles["go-development"]["latest"]
        self.assertEqual(len(go_bundle["plugins"]), 2)
        self.assertIn({"name": "protoc-gen-go", "version": "1.34.2"}, go_bundle["plugins"])
        self.assertIn({"name": "protoc-gen-go-grpc", "version": "1.5.1"}, go_bundle["plugins"])
        
        # Test python-development bundle
        python_bundle = bundles["python-development"]["latest"]
        self.assertEqual(len(python_bundle["plugins"]), 1)
        self.assertIn({"name": "grpcio-tools", "version": "1.66.2"}, python_bundle["plugins"])
        
        # Test typescript-development bundle
        ts_bundle = bundles["typescript-development"]["latest"]
        self.assertEqual(len(ts_bundle["plugins"]), 1)
        self.assertIn({"name": "protoc-gen-ts", "version": "0.8.7"}, ts_bundle["plugins"])
    
    def test_bundle_oras_refs(self):
        """Test bundle ORAS references are properly formatted."""
        bundles = self.distributor.plugin_bundles
        
        for bundle_name, bundle_versions in bundles.items():
            for version, config in bundle_versions.items():
                oras_ref = config["oras_ref"]
                
                # Should follow expected pattern
                self.assertTrue(oras_ref.startswith("test.registry.local/buck2-protobuf/bundles/"))
                self.assertIn(bundle_name, oras_ref)
                self.assertTrue(oras_ref.endswith(f":{version}"))
                
                # Should have valid digest
                self.assertIn("digest", config)
                self.assertTrue(config["digest"].startswith("sha256:"))


class TestPerformanceAndCaching(unittest.TestCase):
    """Test performance monitoring and caching functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        
        with patch('oras_plugins.OrasClient'), patch('oras_plugins.PluginDownloader'):
            self.distributor = PluginOrasDistributor(
                registry="test.registry.local",
                cache_dir=str(self.cache_dir),
                verbose=False
            )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_metrics_initialization(self):
        """Test metrics are properly initialized."""
        metrics = self.distributor.metrics
        
        expected_keys = [
            "oras_hits", "oras_misses", "http_fallbacks", "cache_hits",
            "total_requests", "avg_oras_time", "avg_http_time", "bundle_downloads"
        ]
        
        for key in expected_keys:
            self.assertIn(key, metrics)
            self.assertEqual(metrics[key], 0)
    
    def test_metrics_calculation(self):
        """Test derived metrics calculation."""
        # Set up test data
        self.distributor.metrics.update({
            "total_requests": 100,
            "oras_hits": 60,
            "http_fallbacks": 30,
            "cache_hits": 10,
        })
        
        metrics = self.distributor.get_performance_metrics()
        
        self.assertEqual(metrics["oras_hit_rate"], 0.6)
        self.assertEqual(metrics["http_fallback_rate"], 0.3)
        self.assertEqual(metrics["cache_hit_rate"], 0.1)
    
    def test_cache_directory_structure(self):
        """Test cache directory structure creation."""
        self.assertTrue(self.distributor.cache_dir.exists())
        
        # Test subdirectory creation
        oras_cache = self.distributor.cache_dir / "oras"
        http_cache = self.distributor.cache_dir / "http"
        
        # These should be created when needed
        self.assertTrue(self.distributor.cache_dir.exists())


def run_performance_benchmark():
    """Run performance benchmarks for plugin operations."""
    print("\n=== Plugin Distribution Performance Benchmark ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        distributor = PluginOrasDistributor(
            registry="oras.birb.homes",
            cache_dir=temp_dir,
            verbose=False
        )
        
        # Test plugin listing performance
        start_time = time.time()
        plugins = distributor.get_supported_plugins()
        list_time = time.time() - start_time
        
        print(f"Plugin listing: {len(plugins)} plugins in {list_time:.4f}s")
        
        # Test bundle listing performance
        start_time = time.time()
        bundles = distributor.get_supported_bundles()
        bundle_list_time = time.time() - start_time
        
        print(f"Bundle listing: {len(bundles)} bundles in {bundle_list_time:.4f}s")
        
        # Test metrics calculation performance
        start_time = time.time()
        metrics = distributor.get_performance_metrics()
        metrics_time = time.time() - start_time
        
        print(f"Metrics calculation: {len(metrics)} metrics in {metrics_time:.4f}s")


def main():
    """Main test runner."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ORAS Plugin Distribution Tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmarks")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Configure test verbosity
    verbosity = 2 if args.verbose else 1
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add unit tests
    test_suite.addTest(unittest.makeSuite(TestPluginOrasDistributor))
    test_suite.addTest(unittest.makeSuite(TestPluginBundles))
    test_suite.addTest(unittest.makeSuite(TestPerformanceAndCaching))
    
    # Add integration tests if requested
    if args.integration:
        test_suite.addTest(unittest.makeSuite(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(test_suite)
    
    # Run benchmarks if requested
    if args.benchmark:
        run_performance_benchmark()
    
    # Exit with appropriate code
    exit_code = 0 if result.wasSuccessful() else 1
    return exit_code


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
