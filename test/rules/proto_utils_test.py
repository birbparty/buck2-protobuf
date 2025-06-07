#!/usr/bin/env python3
"""
Unit tests for protobuf test utilities.

This module tests the functionality of the test utilities to ensure
they work correctly for validating Buck2 protobuf rule behavior.
"""

import unittest
import tempfile
from pathlib import Path

from test.test_utils import (
    ProtoTestCase,
    create_test_proto_file,
    create_test_buck_file,
    assert_files_exist,
    assert_files_not_exist,
    assert_proto_compiles,
    run_command,
    run_buck2_command,
    measure_performance,
    create_proto_with_deps,
    create_large_proto,
    validate_buck2_output,
    get_file_size,
    wait_for_file,
    TestTimer,
    generate_test_protos,
)


class TestProtoUtilities(ProtoTestCase):
    """Test the proto testing utilities."""
    
    def test_create_test_proto_file(self):
        """Test creating proto files."""
        content = """
syntax = "proto3";
package test;
message TestMessage {
  int32 id = 1;
}
"""
        proto_path = create_test_proto_file(content, "test.proto", self.test_workspace)
        self.assertTrue(Path(proto_path).exists())
        
        with open(proto_path, "r") as f:
            self.assertIn("message TestMessage", f.read())
    
    def test_create_test_buck_file(self):
        """Test creating BUCK files."""
        content = """
load("//rules:proto.bzl", "proto_library")

proto_library(
    name = "test_proto",
    srcs = ["test.proto"],
)
"""
        buck_path = create_test_buck_file(content, self.test_workspace)
        self.assertTrue(Path(buck_path).exists())
        
        with open(buck_path, "r") as f:
            self.assertIn("proto_library", f.read())
    
    def test_assert_files_exist(self):
        """Test file existence assertions."""
        # Create test files
        test_file = self.test_workspace / "test_file.txt"
        test_file.write_text("test content")
        
        # Should pass
        assert_files_exist([str(test_file)])
        
        # Should fail
        with self.assertRaises(AssertionError):
            assert_files_exist([str(test_file), "nonexistent_file.txt"])
    
    def test_assert_files_not_exist(self):
        """Test file non-existence assertions."""
        # Should pass
        assert_files_not_exist(["nonexistent_file.txt"])
        
        # Create a file that shouldn't exist
        test_file = self.test_workspace / "should_not_exist.txt"
        test_file.write_text("content")
        
        # Should fail
        with self.assertRaises(AssertionError):
            assert_files_not_exist([str(test_file)])
    
    def test_run_command(self):
        """Test running commands."""
        result = run_command(["echo", "hello world"])
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("hello world", result["stdout"])
    
    def test_run_command_timeout(self):
        """Test command timeout."""
        result = run_command(["sleep", "10"], timeout=0.1)
        self.assertEqual(result["exit_code"], 124)  # Timeout exit code
        self.assertIn("timed out", result["stderr"])
    
    def test_run_command_not_found(self):
        """Test command not found."""
        result = run_command(["nonexistent_command_xyz"])
        self.assertEqual(result["exit_code"], 127)  # Command not found
        self.assertIn("Command not found", result["stderr"])
    
    def test_measure_performance(self):
        """Test performance measurement."""
        def test_function(x, y):
            return x + y
        
        metrics = measure_performance(test_function, 2, 3)
        
        self.assertEqual(metrics["result"], 5)
        self.assertGreater(metrics["execution_time_ms"], 0)
        self.assertIsInstance(metrics["memory_delta_kb"], int)
    
    def test_create_proto_with_deps(self):
        """Test creating proto with dependencies."""
        # Create base proto first
        base_content = """
syntax = "proto3";
package base;
message BaseMessage {
  int32 id = 1;
}
"""
        create_test_proto_file(base_content, "base.proto", self.test_workspace)
        
        # Create derived proto
        derived_path = create_proto_with_deps("derived", ["base.proto"], self.test_workspace)
        
        self.assertTrue(Path(derived_path).exists())
        with open(derived_path, "r") as f:
            content = f.read()
            self.assertIn('import "base.proto"', content)
            self.assertIn("DerivedMessage", content)
    
    def test_create_large_proto(self):
        """Test creating large proto files."""
        large_proto_path = create_large_proto(num_fields=50, workspace=self.test_workspace)
        
        self.assertTrue(Path(large_proto_path).exists())
        
        with open(large_proto_path, "r") as f:
            content = f.read()
            self.assertIn("LargeMessage", content)
            self.assertIn("field_49", content)  # Should have 50 fields (0-49)
    
    def test_validate_buck2_output(self):
        """Test Buck2 output validation."""
        output = "BUILD SUCCEEDED\nBuilt 5 targets"
        
        # Should pass
        self.assertTrue(validate_buck2_output(output, ["BUILD SUCCEEDED", "Built"]))
        
        # Should fail
        with self.assertRaises(AssertionError):
            validate_buck2_output(output, ["BUILD FAILED"])
    
    def test_get_file_size(self):
        """Test file size measurement."""
        test_file = self.test_workspace / "size_test.txt"
        test_content = "a" * 100
        test_file.write_text(test_content)
        
        size = get_file_size(str(test_file))
        self.assertEqual(size, 100)
        
        # Non-existent file
        self.assertEqual(get_file_size("nonexistent.txt"), 0)
    
    def test_wait_for_file(self):
        """Test waiting for file creation."""
        import threading
        import time
        
        test_file = self.test_workspace / "delayed_file.txt"
        
        def create_file_delayed():
            time.sleep(0.1)
            test_file.write_text("delayed content")
        
        # Start thread to create file
        thread = threading.Thread(target=create_file_delayed)
        thread.start()
        
        # Wait for file
        self.assertTrue(wait_for_file(str(test_file), timeout=1.0))
        
        thread.join()
        
        # Test timeout
        self.assertFalse(wait_for_file("never_created_file.txt", timeout=0.1))
    
    def test_timer(self):
        """Test TestTimer context manager."""
        import time
        
        with TestTimer("test_operation") as timer:
            time.sleep(0.01)  # Sleep for 10ms
        
        self.assertGreater(timer.elapsed_ms, 5)  # Should be at least 5ms
        self.assertLess(timer.elapsed_ms, 100)  # Should be less than 100ms
    
    def test_generate_test_protos(self):
        """Test generating multiple test protos."""
        proto_files = generate_test_protos(self.test_workspace, count=3)
        
        self.assertEqual(len(proto_files), 3)
        
        for i, proto_path in enumerate(proto_files):
            self.assertTrue(Path(proto_path).exists())
            with open(proto_path, "r") as f:
                content = f.read()
                self.assertIn(f"TestMessage{i}", content)
                self.assertIn(f"TestEnum{i}", content)


class TestAssertProtoCompiles(unittest.TestCase):
    """Test proto compilation validation."""
    
    def test_valid_proto_compiles(self):
        """Test that valid proto content compiles."""
        valid_proto = """
syntax = "proto3";
package test.valid;

message ValidMessage {
  int32 id = 1;
  string name = 2;
}
"""
        # Should not raise exception
        assert_proto_compiles(valid_proto)
    
    def test_invalid_proto_fails(self):
        """Test that invalid proto content fails compilation."""
        invalid_proto = """
syntax = "proto3";
package test.invalid;

message InvalidMessage {
  invalid_type field = 1;  // This should cause compilation to fail
}
"""
        # Should raise AssertionError
        with self.assertRaises(AssertionError):
            assert_proto_compiles(invalid_proto)


class TestBuck2Integration(unittest.TestCase):
    """Test Buck2 command integration."""
    
    def test_run_buck2_command(self):
        """Test running Buck2 commands."""
        # Test a simple Buck2 command that should work
        result = run_buck2_command(["--help"])
        
        # Buck2 help should return 0 and contain usage info
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("buck2", result["stdout"].lower())


if __name__ == "__main__":
    unittest.main()
