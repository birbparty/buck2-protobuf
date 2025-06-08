#!/usr/bin/env python3
"""
Test script for updated tool versions.

This script validates that all updated tool versions work correctly
and that the new checksums are accurate.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Import our updated tools
from oras_protoc import ProtocOrasDistributor
from oras_plugins import PluginOrasDistributor
from update_tool_versions import VersionUpdater


class ToolVersionTester:
    """Test updated tool versions for functionality and compatibility."""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results = {}
        
        # Initialize distributors
        self.protoc_dist = ProtocOrasDistributor(verbose=verbose)
        self.plugin_dist = PluginOrasDistributor(verbose=verbose)
        self.version_updater = VersionUpdater(verbose=verbose)
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[tool-test] {message}", file=sys.stderr)
    
    def test_protoc_versions(self) -> Dict[str, bool]:
        """Test all protoc versions."""
        self.log("Testing protoc versions...")
        
        # Test latest versions
        test_versions = ["30.2", "31.0", "31.1"]
        results = {}
        
        for version in test_versions:
            self.log(f"Testing protoc {version}")
            
            try:
                # Get protoc binary
                protoc_path = self.protoc_dist.get_protoc(version)
                
                # Test basic functionality
                result = subprocess.run([
                    protoc_path, "--version"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    version_output = result.stdout.strip()
                    expected_version = f"libprotoc {version}"
                    
                    if expected_version in version_output:
                        results[f"protoc-{version}"] = True
                        self.log(f"✓ protoc {version}: {version_output}")
                    else:
                        results[f"protoc-{version}"] = False
                        self.log(f"✗ protoc {version}: version mismatch")
                else:
                    results[f"protoc-{version}"] = False
                    self.log(f"✗ protoc {version}: failed to run")
                    
            except Exception as e:
                results[f"protoc-{version}"] = False
                self.log(f"✗ protoc {version}: {e}")
        
        return results
    
    def test_plugin_versions(self) -> Dict[str, bool]:
        """Test updated plugin versions."""
        self.log("Testing plugin versions...")
        
        results = {}
        
        # Test protoc-gen-go latest version
        try:
            self.log("Testing protoc-gen-go 1.36.6")
            plugin_path = self.plugin_dist.get_plugin("protoc-gen-go", "1.36.6")
            
            # Test basic functionality
            result = subprocess.run([
                plugin_path, "--version"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                results["protoc-gen-go-1.36.6"] = True
                self.log(f"✓ protoc-gen-go 1.36.6: works")
            else:
                results["protoc-gen-go-1.36.6"] = False
                self.log(f"✗ protoc-gen-go 1.36.6: failed to run")
                
        except Exception as e:
            results["protoc-gen-go-1.36.6"] = False
            self.log(f"✗ protoc-gen-go 1.36.6: {e}")
        
        # Test protoc-gen-go-grpc
        try:
            self.log("Testing protoc-gen-go-grpc 1.5.1")
            plugin_path = self.plugin_dist.get_plugin("protoc-gen-go-grpc", "1.5.1")
            
            # For gRPC plugin, just check it exists and is executable
            if os.path.exists(plugin_path) and os.access(plugin_path, os.X_OK):
                results["protoc-gen-go-grpc-1.5.1"] = True
                self.log(f"✓ protoc-gen-go-grpc 1.5.1: works")
            else:
                results["protoc-gen-go-grpc-1.5.1"] = False
                self.log(f"✗ protoc-gen-go-grpc 1.5.1: not executable")
                
        except Exception as e:
            results["protoc-gen-go-grpc-1.5.1"] = False
            self.log(f"✗ protoc-gen-go-grpc 1.5.1: {e}")
        
        return results
    
    def test_version_research(self) -> Dict[str, bool]:
        """Test the version research functionality."""
        self.log("Testing version research...")
        
        try:
            # Test GitHub API research
            latest = self.version_updater.research_github_latest_release("protocolbuffers/protobuf")
            
            if latest and latest.startswith("31."):
                return {"version-research": True}
            else:
                return {"version-research": False}
                
        except Exception as e:
            self.log(f"Version research failed: {e}")
            return {"version-research": False}
    
    def test_checksum_validation(self) -> Dict[str, bool]:
        """Test that checksums are correctly calculated and validated."""
        self.log("Testing checksum validation...")
        
        try:
            # Test a known URL with checksum calculation
            test_url = "https://github.com/protocolbuffers/protobuf/releases/download/v31.1/protoc-31.1-linux-x86_64.zip"
            
            checksum = self.version_updater.calculate_sha256_from_url(test_url)
            expected = "96553041f1a91ea0efee963cb16f462f5985b4d65365f3907414c360044d8065"
            
            if checksum == expected:
                return {"checksum-validation": True}
            else:
                self.log(f"Checksum mismatch: got {checksum}, expected {expected}")
                return {"checksum-validation": False}
                
        except Exception as e:
            self.log(f"Checksum validation failed: {e}")
            return {"checksum-validation": False}
    
    def test_compilation_workflow(self) -> Dict[str, bool]:
        """Test end-to-end compilation workflow with new tools."""
        self.log("Testing compilation workflow...")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create a simple proto file
                proto_file = temp_path / "test.proto"
                proto_content = '''
syntax = "proto3";

package test;

message TestMessage {
  string name = 1;
  int32 value = 2;
}

service TestService {
  rpc GetTest(TestMessage) returns (TestMessage);
}
'''
                with open(proto_file, 'w') as f:
                    f.write(proto_content)
                
                # Get tools
                protoc_path = self.protoc_dist.get_protoc("31.1")
                protoc_gen_go_path = self.plugin_dist.get_plugin("protoc-gen-go", "1.36.6")
                
                # Test Go code generation
                go_out = temp_path / "go_out"
                go_out.mkdir()
                
                result = subprocess.run([
                    protoc_path,
                    f"--plugin=protoc-gen-go={protoc_gen_go_path}",
                    f"--go_out={go_out}",
                    f"--go_opt=paths=source_relative",
                    str(proto_file)
                ], capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    # Check if Go file was generated
                    go_file = go_out / "test.pb.go"
                    if go_file.exists():
                        self.log("✓ Go code generation successful")
                        return {"compilation-workflow": True}
                    else:
                        self.log("✗ Go file not generated")
                        return {"compilation-workflow": False}
                else:
                    self.log(f"✗ Compilation failed: {result.stderr}")
                    return {"compilation-workflow": False}
                    
        except Exception as e:
            self.log(f"Compilation workflow failed: {e}")
            return {"compilation-workflow": False}
    
    def test_backward_compatibility(self) -> Dict[str, bool]:
        """Test that updated tools work with existing configurations."""
        self.log("Testing backward compatibility...")
        
        try:
            # Test that old and new protoc versions can compile the same proto
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create proto file
                proto_file = temp_path / "compat.proto"
                proto_content = '''
syntax = "proto3";

message CompatTest {
  string field = 1;
}
'''
                with open(proto_file, 'w') as f:
                    f.write(proto_content)
                
                # Test with different protoc versions
                versions_to_test = ["25.1", "31.1"]  # Old and new
                outputs = {}
                
                for version in versions_to_test:
                    try:
                        protoc_path = self.protoc_dist.get_protoc(version)
                        out_dir = temp_path / f"out_{version.replace('.', '_')}"
                        out_dir.mkdir()
                        
                        result = subprocess.run([
                            protoc_path,
                            f"--descriptor_set_out={out_dir}/desc.pb",
                            str(proto_file)
                        ], capture_output=True, text=True, timeout=30)
                        
                        if result.returncode == 0:
                            outputs[version] = (out_dir / "desc.pb").read_bytes()
                            self.log(f"✓ protoc {version} compiled successfully")
                        else:
                            self.log(f"✗ protoc {version} failed")
                            return {"backward-compatibility": False}
                            
                    except Exception as e:
                        self.log(f"✗ protoc {version} error: {e}")
                        return {"backward-compatibility": False}
                
                # Check that both versions produced output
                if len(outputs) == 2:
                    self.log("✓ Backward compatibility maintained")
                    return {"backward-compatibility": True}
                else:
                    return {"backward-compatibility": False}
                    
        except Exception as e:
            self.log(f"Backward compatibility test failed: {e}")
            return {"backward-compatibility": False}
    
    def run_all_tests(self) -> Dict[str, Dict[str, bool]]:
        """Run all tests and return comprehensive results."""
        self.log("Starting comprehensive tool version tests...")
        
        all_results = {}
        
        # Test individual components
        all_results["protoc_versions"] = self.test_protoc_versions()
        all_results["plugin_versions"] = self.test_plugin_versions()
        all_results["version_research"] = self.test_version_research()
        all_results["checksum_validation"] = self.test_checksum_validation()
        
        # Test workflows
        all_results["compilation_workflow"] = self.test_compilation_workflow()
        all_results["backward_compatibility"] = self.test_backward_compatibility()
        
        self.results = all_results
        return all_results
    
    def print_results_summary(self) -> None:
        """Print a formatted summary of test results."""
        if not self.results:
            print("No test results available")
            return
        
        print("\n" + "="*60)
        print("TOOL VERSION UPDATE TEST RESULTS")
        print("="*60)
        
        total_tests = 0
        passed_tests = 0
        
        for category, tests in self.results.items():
            print(f"\n{category.upper().replace('_', ' ')}:")
            
            for test_name, result in tests.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"  {test_name}: {status}")
                
                total_tests += 1
                if result:
                    passed_tests += 1
        
        print(f"\n" + "="*60)
        print(f"SUMMARY: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            print("🎉 ALL TESTS PASSED! Tool updates are working correctly.")
        else:
            print("⚠️  Some tests failed. Please review the results above.")
        
        print("="*60)


def main():
    """Main entry point for tool version testing."""
    parser = argparse.ArgumentParser(description="Test updated tool versions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--test", help="Run specific test category")
    parser.add_argument("--quick", action="store_true", help="Run only quick tests")
    
    args = parser.parse_args()
    
    try:
        tester = ToolVersionTester(verbose=args.verbose)
        
        if args.test:
            # Run specific test
            if args.test == "protoc":
                results = {"protoc_versions": tester.test_protoc_versions()}
            elif args.test == "plugins":
                results = {"plugin_versions": tester.test_plugin_versions()}
            elif args.test == "research":
                results = {"version_research": tester.test_version_research()}
            elif args.test == "checksums":
                results = {"checksum_validation": tester.test_checksum_validation()}
            elif args.test == "workflow":
                results = {"compilation_workflow": tester.test_compilation_workflow()}
            elif args.test == "compatibility":
                results = {"backward_compatibility": tester.test_backward_compatibility()}
            else:
                print(f"Unknown test: {args.test}")
                sys.exit(1)
                
            tester.results = results
        
        elif args.quick:
            # Run quick tests only
            results = {}
            results["version_research"] = tester.test_version_research()
            results["checksum_validation"] = tester.test_checksum_validation()
            tester.results = results
        
        else:
            # Run all tests
            tester.run_all_tests()
        
        # Print results
        tester.print_results_summary()
        
        # Exit with appropriate code
        if tester.results:
            all_passed = all(
                all(test_results.values()) 
                for test_results in tester.results.values()
            )
            sys.exit(0 if all_passed else 1)
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
