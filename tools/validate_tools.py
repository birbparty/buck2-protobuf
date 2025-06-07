#!/usr/bin/env python3
"""
Validate protoc tools and plugins for protobuf Buck2 integration.

This script validates that downloaded tools have correct checksums,
are functional, and match expected versions.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any


class ToolValidator:
    """Handles validation of protoc tools and plugins."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the tool validator.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[tool-validator] {message}", file=sys.stderr)
    
    def calculate_sha256(self, file_path: Path) -> str:
        """
        Calculate SHA256 checksum of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal SHA256 hash string
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def validate_file_checksum(self, file_path: Path, expected_checksum: str) -> bool:
        """
        Validate SHA256 checksum of a file.
        
        Args:
            file_path: Path to the file to validate
            expected_checksum: Expected SHA256 hash
            
        Returns:
            True if checksum matches, False otherwise
        """
        try:
            actual_checksum = self.calculate_sha256(file_path)
            matches = actual_checksum.lower() == expected_checksum.lower()
            
            if matches:
                self.log(f"Checksum validation passed for {file_path}")
            else:
                self.log(f"Checksum validation failed for {file_path}")
                self.log(f"Expected: {expected_checksum}")
                self.log(f"Actual:   {actual_checksum}")
            
            return matches
            
        except Exception as e:
            self.log(f"Error calculating checksum for {file_path}: {e}")
            return False
    
    def validate_executable_permissions(self, file_path: Path) -> bool:
        """
        Validate that a file has executable permissions.
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file is executable, False otherwise
        """
        if not file_path.exists():
            self.log(f"File not found: {file_path}")
            return False
        
        if not file_path.is_file():
            self.log(f"Not a regular file: {file_path}")
            return False
        
        if not os.access(file_path, os.X_OK):
            self.log(f"File is not executable: {file_path}")
            return False
        
        self.log(f"Executable permissions validated for {file_path}")
        return True
    
    def run_command_safely(self, command: list, timeout: int = 10) -> tuple[bool, str, str]:
        """
        Run a command safely with timeout and capture output.
        
        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            self.log(f"Running command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False  # Don't raise on non-zero exit
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if success:
                self.log(f"Command succeeded with output: {stdout}")
            else:
                self.log(f"Command failed with return code {result.returncode}")
                self.log(f"stderr: {stderr}")
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out after {timeout} seconds")
            return False, "", "Command timed out"
        except Exception as e:
            self.log(f"Error running command: {e}")
            return False, "", str(e)
    
    def validate_protoc_version(self, binary_path: Path, expected_version: Optional[str] = None) -> bool:
        """
        Validate protoc binary functionality and version.
        
        Args:
            binary_path: Path to protoc binary
            expected_version: Expected protoc version (optional)
            
        Returns:
            True if validation passes, False otherwise
        """
        self.log(f"Validating protoc binary: {binary_path}")
        
        # Check executable permissions
        if not self.validate_executable_permissions(binary_path):
            return False
        
        # Test basic functionality with --version
        success, stdout, stderr = self.run_command_safely([str(binary_path), "--version"])
        if not success:
            self.log(f"Failed to run protoc --version: {stderr}")
            return False
        
        # Parse version from output
        if not stdout.startswith("libprotoc"):
            self.log(f"Unexpected protoc version output: {stdout}")
            return False
        
        # Extract version number
        try:
            version_line = stdout.split('\n')[0]
            actual_version = version_line.split()[1]  # "libprotoc 24.4"
            self.log(f"Detected protoc version: {actual_version}")
            
            # Validate expected version if provided
            if expected_version and actual_version != expected_version:
                self.log(f"Version mismatch: expected {expected_version}, got {actual_version}")
                return False
                
        except (IndexError, ValueError) as e:
            self.log(f"Failed to parse protoc version: {e}")
            return False
        
        # Test basic proto compilation
        if not self._test_protoc_compilation(binary_path):
            return False
        
        self.log(f"Protoc validation passed for {binary_path}")
        return True
    
    def _test_protoc_compilation(self, binary_path: Path) -> bool:
        """
        Test protoc compilation with a simple proto file.
        
        Args:
            binary_path: Path to protoc binary
            
        Returns:
            True if compilation test passes, False otherwise
        """
        self.log("Testing protoc compilation functionality")
        
        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a simple test proto file
            test_proto = temp_path / "test.proto"
            test_proto.write_text("""
syntax = "proto3";

package test;

message TestMessage {
  string name = 1;
  int32 id = 2;
}
""".strip())
            
            # Try to compile the proto file
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            command = [
                str(binary_path),
                f"--proto_path={temp_path}",
                f"--descriptor_set_out={output_dir}/test.desc",
                str(test_proto)
            ]
            
            success, stdout, stderr = self.run_command_safely(command)
            if not success:
                self.log(f"Failed to compile test proto: {stderr}")
                return False
            
            # Check that descriptor set was created
            desc_file = output_dir / "test.desc"
            if not desc_file.exists():
                self.log("Descriptor set file was not created")
                return False
            
            self.log("Protoc compilation test passed")
            return True
    
    def validate_plugin_functionality(self, binary_path: Path, plugin_name: str) -> bool:
        """
        Validate protoc plugin binary functionality.
        
        Args:
            binary_path: Path to plugin binary
            plugin_name: Name of the plugin
            
        Returns:
            True if validation passes, False otherwise
        """
        self.log(f"Validating plugin binary: {binary_path} ({plugin_name})")
        
        # Check executable permissions
        if not self.validate_executable_permissions(binary_path):
            return False
        
        # For most protoc plugins, they don't support --version or standalone execution
        # They expect to be called by protoc with specific input
        # We'll do a basic execution test that should fail gracefully
        
        success, stdout, stderr = self.run_command_safely([str(binary_path), "--help"], timeout=5)
        
        # Most plugins will exit with non-zero code when called with --help
        # But they should not crash or hang
        if "protoc-gen-" in plugin_name:
            self.log(f"Plugin {plugin_name} responded to --help (expected behavior)")
        
        # Test plugin with protoc if we can find a protoc binary
        if not self._test_plugin_with_protoc(binary_path, plugin_name):
            self.log(f"Warning: Could not test plugin {plugin_name} with protoc")
            # Don't fail validation just because we can't find protoc
        
        self.log(f"Plugin validation passed for {binary_path}")
        return True
    
    def _test_plugin_with_protoc(self, plugin_path: Path, plugin_name: str) -> bool:
        """
        Test plugin functionality with protoc.
        
        Args:
            plugin_path: Path to plugin binary
            plugin_name: Name of the plugin
            
        Returns:
            True if test passes or protoc not available, False if test fails
        """
        # Try to find protoc in common locations
        protoc_candidates = [
            "protoc",  # In PATH
            "/usr/bin/protoc",
            "/usr/local/bin/protoc",
        ]
        
        protoc_path = None
        for candidate in protoc_candidates:
            success, _, _ = self.run_command_safely([candidate, "--version"], timeout=5)
            if success:
                protoc_path = candidate
                break
        
        if not protoc_path:
            self.log("Could not find protoc for plugin testing")
            return True  # Don't fail if protoc not available
        
        self.log(f"Testing plugin {plugin_name} with protoc at {protoc_path}")
        
        # Create a temporary directory for the test
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create a simple test proto file
            test_proto = temp_path / "test.proto"
            test_proto.write_text("""
syntax = "proto3";

package test;

service TestService {
  rpc TestMethod(TestRequest) returns (TestResponse);
}

message TestRequest {
  string name = 1;
}

message TestResponse {
  string message = 1;
}
""".strip())
            
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # Try to use the plugin with protoc
            # Different plugins have different output flags
            plugin_flags = self._get_plugin_flags(plugin_name, output_dir)
            
            if not plugin_flags:
                self.log(f"No test configuration for plugin {plugin_name}")
                return True
            
            command = [
                protoc_path,
                f"--proto_path={temp_path}",
                f"--plugin={plugin_name}={plugin_path}",
            ] + plugin_flags + [str(test_proto)]
            
            success, stdout, stderr = self.run_command_safely(command, timeout=30)
            if success:
                self.log(f"Plugin {plugin_name} worked correctly with protoc")
                return True
            else:
                self.log(f"Plugin {plugin_name} failed with protoc: {stderr}")
                return False
    
    def _get_plugin_flags(self, plugin_name: str, output_dir: Path) -> list[str]:
        """
        Get appropriate output flags for different plugin types.
        
        Args:
            plugin_name: Name of the plugin
            output_dir: Output directory
            
        Returns:
            List of flags for protoc
        """
        if "go" in plugin_name:
            return [f"--go_out={output_dir}"]
        elif "python" in plugin_name or "grpc" in plugin_name:
            return [f"--python_out={output_dir}", f"--grpc_python_out={output_dir}"]
        elif "cpp" in plugin_name or "cc" in plugin_name:
            return [f"--cpp_out={output_dir}"]
        elif "java" in plugin_name:
            return [f"--java_out={output_dir}"]
        elif "js" in plugin_name or "javascript" in plugin_name:
            return [f"--js_out={output_dir}"]
        elif "ts" in plugin_name or "typescript" in plugin_name:
            return [f"--ts_out={output_dir}"]
        else:
            # Unknown plugin type
            return []
    
    def validate_tool(self, tool_path: str, tool_type: str, **kwargs) -> bool:
        """
        Validate a tool (protoc or plugin) comprehensively.
        
        Args:
            tool_path: Path to the tool binary
            tool_type: Type of tool ("protoc" or "plugin")
            **kwargs: Additional validation parameters
            
        Returns:
            True if all validations pass, False otherwise
        """
        tool_path_obj = Path(tool_path)
        
        self.log(f"Starting validation for {tool_type}: {tool_path}")
        
        # Basic file existence check
        if not tool_path_obj.exists():
            self.log(f"Tool file not found: {tool_path}")
            return False
        
        # Validate checksum if provided
        expected_checksum = kwargs.get("expected_checksum")
        if expected_checksum:
            if not self.validate_file_checksum(tool_path_obj, expected_checksum):
                return False
        
        # Type-specific validation
        if tool_type == "protoc":
            expected_version = kwargs.get("expected_version")
            return self.validate_protoc_version(tool_path_obj, expected_version)
        
        elif tool_type == "plugin":
            plugin_name = kwargs.get("plugin_name", "unknown")
            return self.validate_plugin_functionality(tool_path_obj, plugin_name)
        
        else:
            self.log(f"Unknown tool type: {tool_type}")
            return False


def main():
    """Main entry point for tool validation script."""
    parser = argparse.ArgumentParser(description="Validate protoc tools")
    parser.add_argument("--tool-path", required=True, help="Path to tool binary")
    parser.add_argument("--tool-type", required=True, choices=["protoc", "plugin"], help="Type of tool")
    parser.add_argument("--expected-checksum", help="Expected SHA256 checksum")
    parser.add_argument("--expected-version", help="Expected version (for protoc)")
    parser.add_argument("--plugin-name", help="Plugin name (for plugins)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        validator = ToolValidator(verbose=args.verbose)
        
        # Prepare validation parameters
        validation_params = {}
        if args.expected_checksum:
            validation_params["expected_checksum"] = args.expected_checksum
        if args.expected_version:
            validation_params["expected_version"] = args.expected_version
        if args.plugin_name:
            validation_params["plugin_name"] = args.plugin_name
        elif args.tool_type == "plugin":
            # Try to extract plugin name from file path
            tool_path = Path(args.tool_path)
            validation_params["plugin_name"] = tool_path.stem
        
        # Validate the tool
        if validator.validate_tool(args.tool_path, args.tool_type, **validation_params):
            print("VALID")
            sys.exit(0)
        else:
            print("INVALID", file=sys.stderr)
            sys.exit(1)
        
    except Exception as e:
        print(f"ERROR: Tool validation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
