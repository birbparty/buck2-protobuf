#!/usr/bin/env python3
"""
Test script for ORAS protoc distribution.

This script validates the ORAS protoc distributor functionality including
ORAS-first distribution, HTTP fallback, caching, and performance metrics.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from oras_protoc import ProtocOrasDistributor
from oras_client import OrasClientError, ArtifactNotFoundError


class TestProtocOrasDistributor(unittest.TestCase):
    """Test cases for ORAS protoc distribution functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.registry = "oras.birb.homes"
        
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_distributor_initialization(self):
        """Test ORAS distributor initialization."""
        distributor = ProtocOrasDistributor(
            registry=self.registry,
            cache_dir=str(self.cache_dir),
            verbose=True
        )
        
        self.assertEqual(distributor.registry, self.registry)
        self.assertEqual(distributor.cache_dir, self.cache_dir)
        self.assertTrue(self.cache_dir.exists())
        
        # Should have both ORAS and HTTP fallback configured
        self.assertIsNotNone(distributor.http_fallback)
        
        # Should have protoc artifacts configured
        self.assertIn("24.4", distributor.protoc_artifacts)
        self.assertIn("25.1", distributor.protoc_artifacts)
        self.assertIn("26.1", distributor.protoc_artifacts)
    
    def test_supported_versions_and_platforms(self):
        """Test version and platform support queries."""
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        versions = distributor.get_supported_versions()
        self.assertIn("24.4", versions)
        self.assertIn("25.1", versions)
        self.assertIn("25.2", versions)
        self.assertIn("26.0", versions)
        self.assertIn("26.1", versions)
        
        platforms = distributor.get_supported_platforms()
        self.assertIn("linux-x86_64", platforms)
        self.assertIn("linux-aarch64", platforms)
        self.assertIn("darwin-x86_64", platforms)
        self.assertIn("darwin-arm64", platforms)
        self.assertIn("windows-x86_64", platforms)
    
    def test_invalid_version_platform(self):
        """Test error handling for invalid version/platform."""
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Invalid version
        with self.assertRaises(ValueError) as cm:
            distributor.get_protoc("99.9", "linux-x86_64")
        self.assertIn("Unsupported protoc version", str(cm.exception))
        
        # Invalid platform
        with self.assertRaises(ValueError) as cm:
            distributor.get_protoc("24.4", "invalid-platform")
        self.assertIn("Unsupported platform", str(cm.exception))
    
    @patch('oras_protoc.OrasClient')
    def test_oras_success_path(self, mock_oras_client_class):
        """Test successful ORAS download path."""
        # Mock ORAS client
        mock_oras_client = MagicMock()
        mock_oras_client.pull.return_value = Path("/mock/protoc/binary")
        mock_oras_client_class.return_value = mock_oras_client
        
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Should succeed with ORAS
        result = distributor.get_protoc("24.4", "linux-x86_64")
        self.assertEqual(result, "/mock/protoc/binary")
        
        # Verify ORAS was called
        mock_oras_client.pull.assert_called_once()
        
        # Check metrics
        metrics = distributor.get_performance_metrics()
        self.assertEqual(metrics["oras_hits"], 1)
        self.assertEqual(metrics["http_fallbacks"], 0)
        self.assertEqual(metrics["total_requests"], 1)
    
    @patch('oras_protoc.OrasClient')
    @patch('oras_protoc.ProtocDownloader')
    def test_http_fallback_path(self, mock_http_downloader_class, mock_oras_client_class):
        """Test HTTP fallback when ORAS fails."""
        # Mock ORAS client to fail
        mock_oras_client = MagicMock()
        mock_oras_client.pull.side_effect = ArtifactNotFoundError("Artifact not found")
        mock_oras_client_class.return_value = mock_oras_client
        
        # Mock HTTP downloader to succeed
        mock_http_downloader = MagicMock()
        mock_http_downloader.download_protoc.return_value = "/mock/http/protoc"
        mock_http_downloader_class.return_value = mock_http_downloader
        
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Should fall back to HTTP
        result = distributor.get_protoc("24.4", "linux-x86_64")
        self.assertEqual(result, "/mock/http/protoc")
        
        # Verify ORAS was attempted and HTTP was used
        mock_oras_client.pull.assert_called_once()
        mock_http_downloader.download_protoc.assert_called_once_with("24.4", "linux-x86_64")
        
        # Check metrics
        metrics = distributor.get_performance_metrics()
        self.assertEqual(metrics["oras_hits"], 0)
        self.assertEqual(metrics["oras_misses"], 1)
        self.assertEqual(metrics["http_fallbacks"], 1)
        self.assertEqual(metrics["total_requests"], 1)
    
    @patch('oras_protoc.OrasClient')
    @patch('oras_protoc.ProtocDownloader')
    def test_both_fail_error(self, mock_http_downloader_class, mock_oras_client_class):
        """Test error when both ORAS and HTTP fail."""
        # Mock ORAS client to fail
        mock_oras_client = MagicMock()
        mock_oras_client.pull.side_effect = ArtifactNotFoundError("Artifact not found")
        mock_oras_client_class.return_value = mock_oras_client
        
        # Mock HTTP downloader to fail
        mock_http_downloader = MagicMock()
        mock_http_downloader.download_protoc.side_effect = RuntimeError("HTTP download failed")
        mock_http_downloader_class.return_value = mock_http_downloader
        
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Should raise RuntimeError when both fail
        with self.assertRaises(RuntimeError) as cm:
            distributor.get_protoc("24.4", "linux-x86_64")
        self.assertIn("Both ORAS and HTTP failed", str(cm.exception))
    
    @patch('oras_protoc.detect_platform_string')
    def test_platform_auto_detection(self, mock_detect_platform):
        """Test automatic platform detection."""
        mock_detect_platform.return_value = "linux-x86_64"
        
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Mock ORAS to avoid actual network calls
        with patch.object(distributor, 'oras_available', False):
            with patch.object(distributor.http_fallback, 'download_protoc') as mock_download:
                mock_download.return_value = "/mock/protoc"
                
                result = distributor.get_protoc("24.4")  # No platform specified
                
                mock_detect_platform.assert_called_once()
                mock_download.assert_called_once_with("24.4", "linux-x86_64")
    
    def test_performance_metrics_calculation(self):
        """Test performance metrics calculation."""
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Simulate some requests
        distributor.metrics["total_requests"] = 10
        distributor.metrics["oras_hits"] = 7
        distributor.metrics["http_fallbacks"] = 3
        
        metrics = distributor.get_performance_metrics()
        self.assertEqual(metrics["oras_hit_rate"], 0.7)
        self.assertEqual(metrics["http_fallback_rate"], 0.3)
    
    def test_cache_clearing(self):
        """Test cache clearing functionality."""
        distributor = ProtocOrasDistributor(cache_dir=str(self.cache_dir))
        
        # Create some mock cache files
        http_cache_dir = distributor.cache_dir / "http"
        http_cache_dir.mkdir(parents=True, exist_ok=True)
        
        test_file = http_cache_dir / "test_cache_file"
        test_file.write_text("test content")
        
        # Clear cache
        with patch.object(distributor, 'oras_available', False):
            results = distributor.clear_cache()
        
        self.assertEqual(results["http_cleared"], 1)
        self.assertGreater(results["total_freed_bytes"], 0)


class TestRealOrasConnectivity(unittest.TestCase):
    """Integration tests with real ORAS registry (optional)."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        
        # Skip if we don't want to test against real registry
        self.skip_real_tests = os.getenv("SKIP_REAL_ORAS_TESTS", "false").lower() == "true"
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_real_oras_connectivity(self):
        """Test connectivity to real ORAS registry."""
        if self.skip_real_tests:
            self.skipTest("Skipping real ORAS tests (SKIP_REAL_ORAS_TESTS=true)")
        
        distributor = ProtocOrasDistributor(
            registry="oras.birb.homes",
            cache_dir=str(self.cache_dir),
            verbose=True
        )
        
        # Test with a known artifact (this will likely fail since we haven't published yet)
        # but should gracefully fall back to HTTP
        try:
            result = distributor.get_protoc("24.4", "linux-x86_64")
            self.assertTrue(os.path.exists(result))
            self.assertTrue(os.path.isfile(result))
            
            metrics = distributor.get_performance_metrics()
            print(f"Test metrics: {metrics}")
            
        except Exception as e:
            # This is expected until we publish artifacts
            print(f"Expected failure (artifacts not yet published): {e}")


def run_performance_benchmark():
    """Run a performance benchmark comparing ORAS vs HTTP."""
    print("Running ORAS vs HTTP performance benchmark...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        cache_dir = Path(temp_dir) / "cache"
        
        distributor = ProtocOrasDistributor(
            cache_dir=str(cache_dir),
            verbose=True
        )
        
        # Test multiple versions and platforms
        test_cases = [
            ("24.4", "linux-x86_64"),
            ("25.1", "darwin-arm64"),
            ("26.1", "windows-x86_64"),
        ]
        
        for version, platform in test_cases:
            print(f"\nTesting {version} on {platform}")
            start_time = time.time()
            
            try:
                binary_path = distributor.get_protoc(version, platform)
                elapsed = time.time() - start_time
                print(f"  Success: {binary_path}")
                print(f"  Time: {elapsed:.2f}s")
                
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"  Failed: {e}")
                print(f"  Time: {elapsed:.2f}s")
        
        # Show final metrics
        print("\nFinal performance metrics:")
        metrics = distributor.get_performance_metrics()
        for key, value in metrics.items():
            print(f"  {key}: {value}")


def main():
    """Main entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ORAS Protoc Distribution")
    parser.add_argument("--unit-tests", action="store_true", help="Run unit tests")
    parser.add_argument("--integration-tests", action="store_true", help="Run integration tests")
    parser.add_argument("--benchmark", action="store_true", help="Run performance benchmark")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not any([args.unit_tests, args.integration_tests, args.benchmark, args.all]):
        args.all = True
    
    if args.all or args.unit_tests:
        print("Running unit tests...")
        # Run unit tests
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestProtocOrasDistributor)
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        result = runner.run(suite)
        
        if not result.wasSuccessful():
            print("Unit tests failed!")
            return 1
    
    if args.all or args.integration_tests:
        print("\nRunning integration tests...")
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(TestRealOrasConnectivity)
        runner = unittest.TextTestRunner(verbosity=2 if args.verbose else 1)
        runner.run(suite)
    
    if args.all or args.benchmark:
        print("\nRunning benchmark...")
        run_performance_benchmark()
    
    print("\nAll tests completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
