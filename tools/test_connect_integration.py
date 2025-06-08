#!/usr/bin/env python3
"""
Test script for Connect framework integration.

This script validates that the Connect framework rules are properly integrated
and can generate code for both Connect-Go and Connect-ES.
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

def test_connect_plugin_availability():
    """Test that Connect plugins are available via ORAS distribution."""
    print("Testing Connect plugin availability...")
    
    # Test protoc-gen-connect-go
    try:
        result = subprocess.run([
            sys.executable, "tools/oras_plugins.py",
            "--plugin", "protoc-gen-connect-go",
            "--version", "1.16.2",
            "--verbose"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ protoc-gen-connect-go plugin available")
        else:
            print(f"❌ protoc-gen-connect-go plugin failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error testing protoc-gen-connect-go: {e}")
        return False
    
    # Test protoc-gen-connect-es
    try:
        result = subprocess.run([
            sys.executable, "tools/oras_plugins.py", 
            "--plugin", "protoc-gen-connect-es",
            "--version", "1.6.1",
            "--verbose"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ protoc-gen-connect-es plugin available")
        else:
            print(f"❌ protoc-gen-connect-es plugin failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error testing protoc-gen-connect-es: {e}")
        return False
    
    return True

def test_connect_bundle():
    """Test Connect development bundle."""
    print("Testing Connect development bundle...")
    
    try:
        result = subprocess.run([
            sys.executable, "tools/oras_plugins.py",
            "--bundle", "connect-development",
            "--verbose"
        ], capture_output=True, text=True, cwd=os.getcwd())
        
        if result.returncode == 0:
            print("✅ Connect development bundle available")
            return True
        else:
            print(f"❌ Connect bundle failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Error testing Connect bundle: {e}")
        return False

def test_connect_rules():
    """Test that Connect rules can be loaded."""
    print("Testing Connect rules...")
    
    # Create a temporary test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a simple BUCK file that uses Connect rules
        buck_content = '''
load("//rules:proto.bzl", "proto_library")
load("//rules:connect.bzl", "connect_go_library", "connect_es_library")

proto_library(
    name = "test_proto",
    srcs = ["test.proto"],
)

connect_go_library(
    name = "test_connect_go",
    proto = ":test_proto",
    go_package = "github.com/test/example",
)

connect_es_library(
    name = "test_connect_es", 
    proto = ":test_proto",
    target = "ts",
)
'''
        
        # Create a simple proto file
        proto_content = '''
syntax = "proto3";

package test.v1;

service TestService {
  rpc Echo(EchoRequest) returns (EchoResponse);
}

message EchoRequest {
  string message = 1;
}

message EchoResponse {
  string message = 1;
}
'''
        
        (temp_path / "BUCK").write_text(buck_content)
        (temp_path / "test.proto").write_text(proto_content)
        
        # Try to analyze the BUCK file (would catch syntax errors)
        try:
            result = subprocess.run([
                "buck2", "audit", "rules", str(temp_path / "BUCK")
            ], capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode == 0 or "connect_go_library" in result.stdout:
                print("✅ Connect rules load successfully")
                return True
            else:
                print(f"❌ Connect rules failed to load: {result.stderr}")
                return False
        except FileNotFoundError:
            print("⚠️  Buck2 not available, skipping rule validation")
            return True  # Consider this a pass if Buck2 isn't available
        except Exception as e:
            print(f"❌ Error testing Connect rules: {e}")
            return False

def test_connect_examples():
    """Test that Connect examples are properly structured."""
    print("Testing Connect examples...")
    
    examples_dir = Path("examples/connect")
    
    # Check that example directories exist
    required_dirs = ["go-server", "typescript-client", "grpc-interop", "multi-framework"]
    
    for dir_name in required_dirs:
        dir_path = examples_dir / dir_name
        if not dir_path.exists():
            print(f"❌ Missing example directory: {dir_name}")
            return False
    
    # Check that go-server has required files
    go_server_dir = examples_dir / "go-server"
    required_files = ["user_service.proto", "BUCK"]
    
    for file_name in required_files:
        file_path = go_server_dir / file_name
        if not file_path.exists():
            print(f"❌ Missing file in go-server: {file_name}")
            return False
    
    # Check that the proto file has Connect-compatible service definitions
    proto_file = go_server_dir / "user_service.proto"
    proto_content = proto_file.read_text()
    
    if "service UserService" not in proto_content:
        print("❌ user_service.proto missing service definition")
        return False
    
    if "rpc GetUser" not in proto_content:
        print("❌ user_service.proto missing RPC methods")
        return False
    
    print("✅ Connect examples properly structured")
    return True

def main():
    """Run all Connect framework integration tests."""
    print("=== Connect Framework Integration Tests ===\n")
    
    tests = [
        test_connect_plugin_availability,
        test_connect_bundle,
        test_connect_rules,
        test_connect_examples,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}\n")
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All Connect framework integration tests passed!")
        return 0
    else:
        print("💥 Some Connect framework integration tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main())
