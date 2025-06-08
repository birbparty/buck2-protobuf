#!/usr/bin/env python3
"""
Tests for BSR-ORAS integration and popular dependency resolution.

This module provides comprehensive testing for the BSR dependency resolver,
including ORAS caching, dependency parsing, and Buck2 integration.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
import sys
sys.path.append('.')
from tools.oras_bsr import PopularBSRResolver
from tools.bsr_client import BSRClientError


class TestPopularBSRResolver(unittest.TestCase):
    """Test cases for PopularBSRResolver."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.resolver = PopularBSRResolver(
            oras_registry="test.registry.local",
            cache_dir=self.temp_dir / "cache",
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_supported_dependencies_recognition(self):
        """Test that popular dependencies are correctly recognized."""
        supported_deps = [
            "buf.build/googleapis/googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway",
            "buf.build/envoyproxy/protoc-gen-validate",
            "buf.build/connectrpc/connect",
        ]
        
        for dep in supported_deps:
            self.assertTrue(
                self.resolver.is_supported_dependency(dep),
                f"Should support {dep}"
            )
        
        unsupported_deps = [
            "buf.build/unknown/module",
            "invalid-reference",
            "buf.build/test/unsupported",
        ]
        
        for dep in unsupported_deps:
            self.assertFalse(
                self.resolver.is_supported_dependency(dep),
                f"Should not support {dep}"
            )
    
    def test_bsr_reference_parsing(self):
        """Test BSR reference parsing functionality."""
        test_cases = [
            {
                "ref": "buf.build/googleapis/googleapis",
                "expected": {
                    "base_ref": "buf.build/googleapis/googleapis",
                    "registry": "buf.build",
                    "owner": "googleapis",
                    "module": "googleapis",
                    "version": None,
                    "full_ref": "buf.build/googleapis/googleapis"
                }
            },
            {
                "ref": "buf.build/grpc-ecosystem/grpc-gateway:v2.0.0",
                "expected": {
                    "base_ref": "buf.build/grpc-ecosystem/grpc-gateway",
                    "registry": "buf.build",
                    "owner": "grpc-ecosystem",
                    "module": "grpc-gateway",
                    "version": "v2.0.0",
                    "full_ref": "buf.build/grpc-ecosystem/grpc-gateway:v2.0.0"
                }
            }
        ]
        
        for case in test_cases:
            parsed = self.resolver._parse_bsr_reference(case["ref"])
            for key, expected_value in case["expected"].items():
                self.assertEqual(
                    parsed[key], 
                    expected_value,
                    f"Mismatch for {key} in {case['ref']}"
                )
    
    def test_version_resolution(self):
        """Test version resolution logic."""
        bsr_ref = "buf.build/googleapis/googleapis"
        
        # Test default version
        version = self.resolver._resolve_version(bsr_ref, None)
        self.assertEqual(version, "main")
        
        # Test explicit version
        version = self.resolver._resolve_version(bsr_ref, "v1.0.0")
        self.assertEqual(version, "v1.0.0")
        
        # Test warning for uncommon version
        with patch('builtins.print') as mock_print:
            version = self.resolver._resolve_version(bsr_ref, "v0.9.0")
            self.assertEqual(version, "v0.9.0")
            # Should have logged a warning
            mock_print.assert_called()
    
    def test_oras_reference_conversion(self):
        """Test BSR to ORAS reference conversion."""
        test_cases = [
            {
                "bsr_ref": "buf.build/googleapis/googleapis",
                "version": "main",
                "expected": "test.registry.local/bsr-cache/googleapis-googleapis:main"
            },
            {
                "bsr_ref": "buf.build/grpc-ecosystem/grpc-gateway",
                "version": "v2.0.0",
                "expected": "test.registry.local/bsr-cache/grpc-gateway:v2.0.0"
            }
        ]
        
        for case in test_cases:
            oras_ref = self.resolver._get_oras_reference(case["bsr_ref"], case["version"])
            self.assertEqual(oras_ref, case["expected"])
    
    def test_cache_key_generation(self):
        """Test cache key generation for dependencies."""
        key1 = self.resolver._generate_cache_key("buf.build/googleapis/googleapis", "main")
        key2 = self.resolver._generate_cache_key("buf.build/googleapis/googleapis", "v1.0.0")
        key3 = self.resolver._generate_cache_key("buf.build/grpc-ecosystem/grpc-gateway", "main")
        
        # Keys should be different for different inputs
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key3)
        self.assertNotEqual(key2, key3)
        
        # Keys should be consistent for same inputs
        key1_again = self.resolver._generate_cache_key("buf.build/googleapis/googleapis", "main")
        self.assertEqual(key1, key1_again)
        
        # Keys should be short hash strings
        self.assertEqual(len(key1), 16)
        self.assertTrue(all(c in "0123456789abcdef" for c in key1))
    
    def test_dependency_info_retrieval(self):
        """Test getting dependency information."""
        # Test supported dependency
        info = self.resolver.get_dependency_info("buf.build/googleapis/googleapis")
        self.assertTrue(info["supported"])
        self.assertEqual(info["bsr_ref"], "buf.build/googleapis/googleapis")
        self.assertEqual(info["resolved_version"], "main")
        self.assertIn("description", info)
        
        # Test supported dependency with version
        info = self.resolver.get_dependency_info("buf.build/googleapis/googleapis:v1.0.0")
        self.assertTrue(info["supported"])
        self.assertEqual(info["requested_version"], "v1.0.0")
        self.assertEqual(info["resolved_version"], "v1.0.0")
        
        # Test unsupported dependency
        info = self.resolver.get_dependency_info("buf.build/unknown/module")
        self.assertFalse(info["supported"])
        self.assertIn("error", info)
    
    def test_supported_dependencies_listing(self):
        """Test listing all supported dependencies."""
        deps = self.resolver.list_supported_dependencies()
        
        self.assertGreater(len(deps), 0)
        
        # Check that all expected dependencies are listed
        expected_deps = [
            "buf.build/googleapis/googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway",
            "buf.build/envoyproxy/protoc-gen-validate",
            "buf.build/connectrpc/connect",
        ]
        
        listed_refs = [dep["bsr_ref"] for dep in deps]
        for expected_dep in expected_deps:
            self.assertIn(expected_dep, listed_refs)
        
        # Check that each dependency has required fields
        for dep in deps:
            self.assertIn("bsr_ref", dep)
            self.assertIn("description", dep)
            self.assertIn("default_version", dep)
            self.assertIn("common_versions", dep)
    
    @patch('subprocess.run')
    def test_buf_download_success(self, mock_run):
        """Test successful BSR dependency download via buf CLI."""
        # Mock successful buf export
        mock_run.return_value = Mock(returncode=0, stderr="", stdout="")
        
        # Create some mock proto files in temp directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            google_dir = temp_path / "google" / "api"
            google_dir.mkdir(parents=True)
            
            annotations_file = google_dir / "annotations.proto"
            annotations_file.write_text('syntax = "proto3"; package google.api;')
            
            # Patch the temporary directory creation
            with patch('tempfile.TemporaryDirectory') as mock_temp:
                mock_temp.return_value.__enter__.return_value = temp_dir
                
                result_path = self.resolver._download_bsr_dependency_via_buf(
                    "buf.build/googleapis/googleapis", 
                    "main"
                )
                
                # Check that buf export was called correctly
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                self.assertEqual(call_args[0], "buf")
                self.assertEqual(call_args[1], "export")
                self.assertEqual(call_args[2], "buf.build/googleapis/googleapis:main")
                
                # Check that result path exists and contains proto files
                self.assertTrue(result_path.exists())
    
    @patch('subprocess.run')
    def test_buf_download_failure_with_fallback(self, mock_run):
        """Test BSR dependency download failure with placeholder fallback."""
        # Mock failed buf export
        mock_run.return_value = Mock(returncode=1, stderr="Module not found", stdout="")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch('tempfile.TemporaryDirectory') as mock_temp:
                mock_temp.return_value.__enter__.return_value = temp_dir
                
                result_path = self.resolver._download_bsr_dependency_via_buf(
                    "buf.build/googleapis/googleapis", 
                    "main"
                )
                
                # Should still return a path (with placeholder files)
                self.assertTrue(result_path.exists())
    
    def test_cache_operations(self):
        """Test dependency caching operations."""
        bsr_ref = "buf.build/googleapis/googleapis"
        version = "main"
        
        # Initially no cache
        cached_path = self.resolver._get_cached_dependency(bsr_ref, version)
        self.assertIsNone(cached_path)
        
        # Create a fake proto files directory
        proto_files_path = self.temp_dir / "test_protos"
        proto_files_path.mkdir()
        
        # Cache the dependency
        self.resolver._cache_resolved_dependency(bsr_ref, version, proto_files_path)
        
        # Should now find cached version
        cached_path = self.resolver._get_cached_dependency(bsr_ref, version)
        self.assertEqual(cached_path, proto_files_path)
        
        # Test cache expiration
        cached_path = self.resolver._get_cached_dependency(bsr_ref, version, max_age=0)
        self.assertIsNone(cached_path)
    
    @patch.object(PopularBSRResolver, '_download_bsr_dependency_via_buf')
    def test_resolve_popular_dependency(self, mock_download):
        """Test the main dependency resolution method."""
        # Mock the download method
        mock_proto_path = self.temp_dir / "mock_protos"
        mock_proto_path.mkdir()
        mock_download.return_value = mock_proto_path
        
        # Test resolving a supported dependency
        result_path = self.resolver.resolve_popular_dependency("buf.build/googleapis/googleapis")
        
        self.assertEqual(result_path, mock_proto_path)
        mock_download.assert_called_once_with("buf.build/googleapis/googleapis", "main")
    
    def test_resolve_unsupported_dependency(self):
        """Test resolving an unsupported dependency raises error."""
        with self.assertRaises(ValueError) as context:
            self.resolver.resolve_popular_dependency("buf.build/unknown/module")
        
        self.assertIn("Unsupported BSR dependency", str(context.exception))
    
    @patch.object(PopularBSRResolver, 'resolve_popular_dependency')
    def test_resolve_multiple_dependencies(self, mock_resolve):
        """Test resolving multiple dependencies."""
        # Mock individual resolutions
        mock_paths = {
            "buf.build/googleapis/googleapis": self.temp_dir / "googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway": self.temp_dir / "grpc-gateway",
        }
        
        for path in mock_paths.values():
            path.mkdir()
        
        def side_effect(dep_ref):
            return mock_paths[dep_ref]
        
        mock_resolve.side_effect = side_effect
        
        # Resolve multiple dependencies
        deps = list(mock_paths.keys())
        results = self.resolver.resolve_multiple_dependencies(deps)
        
        self.assertEqual(len(results), 2)
        for dep, expected_path in mock_paths.items():
            self.assertEqual(results[dep], expected_path)
        
        # Check that resolve was called for each dependency
        self.assertEqual(mock_resolve.call_count, 2)
    
    def test_clear_cache_functionality(self):
        """Test cache clearing functionality."""
        # Create some mock cache files
        self.resolver.resolved_deps_cache.mkdir(parents=True, exist_ok=True)
        self.resolver.proto_files_cache.mkdir(parents=True, exist_ok=True)
        
        # Create test files
        test_file1 = self.resolver.resolved_deps_cache / "test1.json"
        test_file1.write_text('{"test": "data"}')
        
        test_dir = self.resolver.proto_files_cache / "test_module"
        test_dir.mkdir()
        
        # Mock ORAS client clear_cache
        with patch.object(self.resolver.oras_client, 'clear_cache', return_value=5):
            cleared = self.resolver.clear_cache()
        
        # Should have cleared local cache items plus ORAS cache
        self.assertGreater(cleared, 0)
        
        # Files should be removed
        self.assertFalse(test_file1.exists())
        self.assertFalse(test_dir.exists())


class TestBSRImplementationIntegration(unittest.TestCase):
    """Test cases for BSR implementation integration with Buck2."""
    
    def test_bsr_reference_validation(self):
        """Test BSR reference validation functions."""
        from rules.private.bsr_impl import validate_bsr_dependencies, is_supported_bsr_dependency
        
        # Valid references
        valid_refs = [
            "buf.build/googleapis/googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway:v2.0.0",
            "registry.example.com/owner/module:latest",
        ]
        
        for ref in valid_refs:
            self.assertTrue(validate_bsr_dependencies([ref]))
        
        # Test supported dependency checking
        self.assertTrue(is_supported_bsr_dependency("buf.build/googleapis/googleapis"))
        self.assertTrue(is_supported_bsr_dependency("buf.build/googleapis/googleapis:v1.0.0"))
        self.assertFalse(is_supported_bsr_dependency("buf.build/unknown/module"))
    
    def test_popular_dependencies_list(self):
        """Test the popular dependencies list."""
        from rules.private.bsr_impl import get_popular_bsr_dependencies
        
        popular_deps = get_popular_bsr_dependencies()
        
        self.assertIsInstance(popular_deps, list)
        self.assertGreater(len(popular_deps), 0)
        
        # Check that expected dependencies are included
        expected_deps = [
            "buf.build/googleapis/googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway",
            "buf.build/envoyproxy/protoc-gen-validate",
            "buf.build/connectrpc/connect",
        ]
        
        for expected_dep in expected_deps:
            self.assertIn(expected_dep, popular_deps)


def run_performance_test():
    """Run basic performance tests for BSR resolution."""
    import time
    
    print("Running BSR resolver performance tests...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        resolver = PopularBSRResolver(
            oras_registry="test.registry.local",
            cache_dir=Path(temp_dir) / "cache",
            verbose=False
        )
        
        # Test dependency info retrieval performance
        deps = [
            "buf.build/googleapis/googleapis",
            "buf.build/grpc-ecosystem/grpc-gateway", 
            "buf.build/envoyproxy/protoc-gen-validate",
            "buf.build/connectrpc/connect",
        ]
        
        start_time = time.time()
        for dep in deps:
            info = resolver.get_dependency_info(dep)
            assert info["supported"], f"Should support {dep}"
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Resolved info for {len(deps)} dependencies in {duration:.3f}s")
        print(f"Average time per dependency: {duration/len(deps):.3f}s")
        
        # Test cache operations performance
        start_time = time.time()
        for i in range(100):
            key = resolver._generate_cache_key(f"test.dep.{i}", "v1.0.0")
            assert len(key) == 16
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Generated 100 cache keys in {duration:.3f}s")
        print(f"Average time per cache key: {duration/100:.6f}s")


if __name__ == "__main__":
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run performance tests
    print("\n" + "="*50)
    run_performance_test()
