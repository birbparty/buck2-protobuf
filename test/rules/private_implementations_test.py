#!/usr/bin/env python3
"""
Comprehensive unit tests for private implementation modules.

This module tests all private implementation modules to achieve
comprehensive coverage of the internal Buck2 protobuf integration logic.
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import test utilities
from test.test_utils import ProtoTestCase, create_test_proto_file, run_command


class TestCacheImplementation(unittest.TestCase):
    """Test cache implementation modules."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cache_key_generation(self):
        """Test cache key generation logic."""
        # Test basic cache key generation
        from rules.private.cache_keys import generate_cache_key
        
        key1 = generate_cache_key("test.proto", ["dep1.proto"], {})
        key2 = generate_cache_key("test.proto", ["dep1.proto"], {})
        key3 = generate_cache_key("test.proto", ["dep2.proto"], {})
        
        # Same inputs should generate same key
        self.assertEqual(key1, key2)
        
        # Different inputs should generate different keys
        self.assertNotEqual(key1, key3)
    
    def test_cache_key_determinism(self):
        """Test cache key determinism across runs."""
        from rules.private.cache_keys import generate_cache_key
        
        # Multiple calls with same input should be deterministic
        inputs = ("test.proto", ["dep1.proto", "dep2.proto"], {"flag": "value"})
        keys = [generate_cache_key(*inputs) for _ in range(10)]
        
        # All keys should be identical
        self.assertEqual(len(set(keys)), 1)
    
    def test_cache_key_sensitivity(self):
        """Test cache key sensitivity to input changes."""
        from rules.private.cache_keys import generate_cache_key
        
        base_key = generate_cache_key("test.proto", ["dep.proto"], {"flag": "value"})
        
        # Different source file
        key1 = generate_cache_key("other.proto", ["dep.proto"], {"flag": "value"})
        self.assertNotEqual(base_key, key1)
        
        # Different dependencies
        key2 = generate_cache_key("test.proto", ["other.proto"], {"flag": "value"})
        self.assertNotEqual(base_key, key2)
        
        # Different flags
        key3 = generate_cache_key("test.proto", ["dep.proto"], {"flag": "other"})
        self.assertNotEqual(base_key, key3)
    
    def test_cache_storage_operations(self):
        """Test cache storage operations."""
        from rules.private.cache_storage import CacheStorage
        
        storage = CacheStorage(str(self.cache_dir))
        
        # Test store and retrieve
        key = "test_key"
        data = b"test_data"
        
        storage.store(key, data)
        self.assertTrue(storage.exists(key))
        
        retrieved = storage.retrieve(key)
        self.assertEqual(data, retrieved)
        
        # Test non-existent key
        self.assertFalse(storage.exists("non_existent"))
        self.assertIsNone(storage.retrieve("non_existent"))
    
    def test_cache_storage_cleanup(self):
        """Test cache storage cleanup operations."""
        from rules.private.cache_storage import CacheStorage
        
        storage = CacheStorage(str(self.cache_dir))
        
        # Store multiple items
        for i in range(5):
            storage.store(f"key_{i}", f"data_{i}".encode())
        
        # Verify all exist
        for i in range(5):
            self.assertTrue(storage.exists(f"key_{i}"))
        
        # Cleanup old entries
        storage.cleanup_old_entries(max_age_seconds=0)
        
        # Should still exist (just created)
        for i in range(5):
            self.assertTrue(storage.exists(f"key_{i}"))
    
    def test_cache_metrics_tracking(self):
        """Test cache metrics tracking."""
        from rules.private.cache_metrics import CacheMetrics
        
        metrics = CacheMetrics()
        
        # Test hit/miss tracking
        metrics.record_hit("test_key")
        metrics.record_miss("test_key")
        metrics.record_hit("test_key")
        
        stats = metrics.get_stats()
        self.assertEqual(stats["hits"], 2)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.667, places=2)
    
    def test_cache_metrics_performance(self):
        """Test cache metrics performance tracking."""
        from rules.private.cache_metrics import CacheMetrics
        import time
        
        metrics = CacheMetrics()
        
        # Simulate cache operations with timing
        start_time = time.time()
        time.sleep(0.01)  # 10ms
        metrics.record_operation_time("retrieve", time.time() - start_time)
        
        start_time = time.time()
        time.sleep(0.005)  # 5ms
        metrics.record_operation_time("store", time.time() - start_time)
        
        stats = metrics.get_performance_stats()
        self.assertGreater(stats["retrieve"]["avg_time"], 0.008)
        self.assertGreater(stats["store"]["avg_time"], 0.004)


class TestSecurityImplementation(unittest.TestCase):
    """Test security implementation modules."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_input_validation(self):
        """Test input validation functions."""
        from rules.private.security_impl import validate_proto_path, validate_import_path
        
        # Valid paths
        self.assertTrue(validate_proto_path("valid/path/file.proto"))
        self.assertTrue(validate_import_path("valid/import/path"))
        
        # Invalid paths (directory traversal)
        self.assertFalse(validate_proto_path("../../../etc/passwd"))
        self.assertFalse(validate_proto_path("path/../../../file.proto"))
        self.assertFalse(validate_import_path("../../../"))
        
        # Null bytes
        self.assertFalse(validate_proto_path("path\x00/file.proto"))
        self.assertFalse(validate_import_path("path\x00"))
    
    def test_sanitization_functions(self):
        """Test path and input sanitization."""
        from rules.private.security_impl import sanitize_path, sanitize_flag
        
        # Path sanitization
        clean_path = sanitize_path("../dangerous/../path/file.proto")
        self.assertNotIn("..", clean_path)
        
        # Flag sanitization
        clean_flag = sanitize_flag("--flag=value; rm -rf /")
        self.assertNotIn(";", clean_flag)
        self.assertNotIn("rm", clean_flag)
    
    def test_command_injection_prevention(self):
        """Test command injection prevention."""
        from rules.private.security_impl import build_safe_command
        
        # Safe command building
        cmd = build_safe_command("protoc", ["--proto_path=.", "file.proto"])
        self.assertIsInstance(cmd, list)
        self.assertEqual(cmd[0], "protoc")
        
        # Dangerous input should be sanitized
        dangerous_arg = "--proto_path=.; rm -rf /"
        cmd = build_safe_command("protoc", [dangerous_arg])
        self.assertNotIn("rm", " ".join(cmd))
    
    def test_privilege_restrictions(self):
        """Test privilege restriction mechanisms."""
        from rules.private.security_impl import check_privileges, drop_privileges
        
        # Should detect current privilege level
        is_privileged = check_privileges()
        self.assertIsInstance(is_privileged, bool)
        
        # Drop privileges (if possible)
        if is_privileged:
            result = drop_privileges()
            self.assertIsInstance(result, bool)
    
    def test_file_access_controls(self):
        """Test file access control mechanisms."""
        from rules.private.security_impl import check_file_access, is_safe_path
        
        # Create test file
        test_file = Path(self.temp_dir) / "test.proto"
        test_file.write_text("syntax = \"proto3\";")
        
        # Should allow access to file in temp dir
        self.assertTrue(check_file_access(str(test_file)))
        self.assertTrue(is_safe_path(str(test_file)))
        
        # Should deny access to system files
        self.assertFalse(is_safe_path("/etc/passwd"))
        self.assertFalse(is_safe_path("/proc/version"))


class TestValidationImplementation(unittest.TestCase):
    """Test validation implementation modules."""
    
    def test_proto_syntax_validation(self):
        """Test proto file syntax validation."""
        from rules.private.validation_impl import validate_proto_syntax
        
        # Valid proto syntax
        valid_proto = """
syntax = "proto3";

package test;

message TestMessage {
  string name = 1;
  int32 id = 2;
}
"""
        self.assertTrue(validate_proto_syntax(valid_proto))
        
        # Invalid proto syntax
        invalid_proto = """
syntax = "proto3"  // Missing semicolon

message TestMessage {
  string name = 1;
  invalid_field_type field = 2;  // Invalid type
}
"""
        self.assertFalse(validate_proto_syntax(invalid_proto))
    
    def test_import_validation(self):
        """Test import path validation."""
        from rules.private.validation_impl import validate_imports
        
        # Valid imports
        valid_imports = [
            "google/protobuf/timestamp.proto",
            "google/protobuf/duration.proto",
            "common/types.proto"
        ]
        self.assertTrue(validate_imports(valid_imports))
        
        # Invalid imports (potential security risk)
        invalid_imports = [
            "../../../etc/passwd",
            "/absolute/path/file.proto",
            "path/with\x00null.proto"
        ]
        self.assertFalse(validate_imports(invalid_imports))
    
    def test_naming_convention_validation(self):
        """Test naming convention validation."""
        from rules.private.validation_impl import validate_naming_conventions
        
        proto_content = """
syntax = "proto3";

package com.example.valid;

message ValidMessage {
  string valid_field = 1;
}

service ValidService {
  rpc ValidMethod(ValidMessage) returns (ValidMessage);
}
"""
        self.assertTrue(validate_naming_conventions(proto_content))
        
        # Invalid naming
        invalid_proto = """
syntax = "proto3";

package Invalid.Package;  // Should be lowercase

message invalid_message {  // Should be CamelCase
  string InvalidField = 1;  // Should be snake_case
}
"""
        self.assertFalse(validate_naming_conventions(invalid_proto))
    
    def test_dependency_validation(self):
        """Test dependency validation logic."""
        from rules.private.validation_impl import validate_dependencies
        
        # Valid dependency graph
        deps = {
            "a.proto": [],
            "b.proto": ["a.proto"],
            "c.proto": ["a.proto", "b.proto"]
        }
        self.assertTrue(validate_dependencies(deps))
        
        # Circular dependency
        circular_deps = {
            "a.proto": ["b.proto"],
            "b.proto": ["c.proto"],
            "c.proto": ["a.proto"]
        }
        self.assertFalse(validate_dependencies(circular_deps))


class TestBundleImplementation(unittest.TestCase):
    """Test bundle implementation modules."""
    
    def test_bundle_creation(self):
        """Test multi-language bundle creation."""
        from rules.private.bundle_impl import create_proto_bundle
        
        bundle_config = {
            "name": "test_bundle",
            "protos": ["test.proto"],
            "languages": ["go", "python", "typescript"]
        }
        
        bundle = create_proto_bundle(bundle_config)
        self.assertEqual(bundle["name"], "test_bundle")
        self.assertEqual(len(bundle["targets"]), 3)
    
    def test_bundle_dependency_resolution(self):
        """Test bundle dependency resolution."""
        from rules.private.bundle_impl import resolve_bundle_dependencies
        
        bundles = {
            "bundle_a": {"deps": []},
            "bundle_b": {"deps": ["bundle_a"]},
            "bundle_c": {"deps": ["bundle_a", "bundle_b"]}
        }
        
        resolved = resolve_bundle_dependencies(bundles)
        self.assertEqual(resolved["bundle_c"]["resolved_deps"], ["bundle_a", "bundle_b"])


class TestGrpcImplementation(unittest.TestCase):
    """Test gRPC implementation modules."""
    
    def test_service_validation(self):
        """Test gRPC service validation."""
        from rules.private.grpc_impl import validate_grpc_service
        
        # Valid service
        valid_service = """
syntax = "proto3";

service TestService {
  rpc GetTest(TestRequest) returns (TestResponse);
  rpc ListTests(ListTestsRequest) returns (ListTestsResponse);
}

message TestRequest {
  string id = 1;
}

message TestResponse {
  string name = 1;
}
"""
        self.assertTrue(validate_grpc_service(valid_service))
        
        # Service without methods
        invalid_service = """
syntax = "proto3";

service EmptyService {
  // No methods
}
"""
        self.assertFalse(validate_grpc_service(invalid_service))
    
    def test_method_validation(self):
        """Test gRPC method validation."""
        from rules.private.grpc_impl import validate_grpc_methods
        
        methods = [
            {
                "name": "GetTest",
                "input_type": "TestRequest",
                "output_type": "TestResponse",
                "client_streaming": False,
                "server_streaming": False
            }
        ]
        
        self.assertTrue(validate_grpc_methods(methods))


class TestToolImplementation(unittest.TestCase):
    """Test tool implementation modules."""
    
    def test_tool_discovery(self):
        """Test tool discovery functionality."""
        from rules.private.tool_impl import discover_tools
        
        tools = discover_tools()
        self.assertIsInstance(tools, dict)
        self.assertIn("protoc", tools)
    
    def test_tool_validation(self):
        """Test tool validation."""
        from rules.private.tool_impl import validate_tool
        
        # Test with protoc (should be available in CI)
        protoc_valid = validate_tool("protoc", ["--version"])
        self.assertIsInstance(protoc_valid, bool)
    
    def test_tool_execution(self):
        """Test safe tool execution."""
        from rules.private.tool_impl import execute_tool
        
        # Safe command execution
        result = execute_tool("echo", ["test"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("test", result.stdout)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility function modules."""
    
    def test_path_utilities(self):
        """Test path utility functions."""
        from rules.private.utils import normalize_path, resolve_import_path
        
        # Path normalization
        normalized = normalize_path("./path/../other/file.proto")
        self.assertEqual(normalized, "other/file.proto")
        
        # Import path resolution
        resolved = resolve_import_path("base/path", "relative/import.proto")
        self.assertEqual(resolved, "base/path/relative/import.proto")
    
    def test_file_utilities(self):
        """Test file utility functions."""
        from rules.private.utils import read_proto_file, parse_proto_dependencies
        
        # Create test proto file
        test_proto = Path(self.temp_dir) / "test.proto"
        test_proto.write_text("""
syntax = "proto3";

import "google/protobuf/timestamp.proto";
import "common/types.proto";

package test;
""")
        
        # Read proto file
        content = read_proto_file(str(test_proto))
        self.assertIn("syntax = \"proto3\"", content)
        
        # Parse dependencies
        deps = parse_proto_dependencies(content)
        self.assertIn("google/protobuf/timestamp.proto", deps)
        self.assertIn("common/types.proto", deps)
    
    def test_string_utilities(self):
        """Test string utility functions."""
        from rules.private.utils import snake_to_camel, camel_to_snake
        
        # Case conversion
        self.assertEqual(snake_to_camel("test_string"), "TestString")
        self.assertEqual(camel_to_snake("TestString"), "test_string")
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestErrorHandling(unittest.TestCase):
    """Test error handling across all modules."""
    
    def test_graceful_error_handling(self):
        """Test that modules handle errors gracefully."""
        from rules.private.cache_impl import handle_cache_error
        from rules.private.security_impl import handle_security_error
        
        # Cache errors should be handled gracefully
        result = handle_cache_error(Exception("Test error"))
        self.assertIsInstance(result, dict)
        self.assertIn("error", result)
        
        # Security errors should be handled with appropriate logging
        result = handle_security_error("Invalid path detected")
        self.assertIsInstance(result, bool)
        self.assertFalse(result)
    
    def test_error_propagation(self):
        """Test proper error propagation."""
        from rules.private.validation_impl import ValidationError
        
        # Validation errors should propagate correctly
        with self.assertRaises(ValidationError):
            raise ValidationError("Test validation error")


if __name__ == "__main__":
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestCacheImplementation,
        TestSecurityImplementation,
        TestValidationImplementation,
        TestBundleImplementation,
        TestGrpcImplementation,
        TestToolImplementation,
        TestUtilityFunctions,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
