#!/usr/bin/env python3
"""
Test utilities for protobuf Buck2 integration.

This module provides common testing utilities and helpers used across
the test suite for comprehensive testing of the protobuf-buck2 integration.
"""

import os
import subprocess
import tempfile
import time
import unittest
import shutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import threading
import resource


class ProtoTestCase(unittest.TestCase):
    """Base test case for protobuf Buck2 integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp(prefix="proto_test_")
        self.original_cwd = os.getcwd()
        # Create a temporary test workspace
        self.test_workspace = Path(self.temp_dir) / "workspace"
        self.test_workspace.mkdir(parents=True, exist_ok=True)
        
        # Initialize Buck2 configuration in test workspace
        self._create_test_buckconfig()
        
    def tearDown(self):
        """Clean up test environment."""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_buckconfig(self):
        """Create a minimal .buckconfig for testing."""
        buckconfig_content = """
[cells]
    root = .

[buildfile]
    name = BUCK

[parser]
    target_platform_detector_spec = target:root//platforms:default
"""
        buckconfig_path = self.test_workspace / ".buckconfig"
        buckconfig_path.write_text(buckconfig_content.strip())
        
        # Create platforms directory and BUCK file
        platforms_dir = self.test_workspace / "platforms"
        platforms_dir.mkdir(exist_ok=True)
        
        platforms_buck = platforms_dir / "BUCK"
        platforms_buck.write_text("""
platform(
    name = "default",
    constraint_values = [],
    visibility = ["PUBLIC"],
)
""".strip())


def create_test_proto_file(content: str, filename: str = "test.proto", workspace: Optional[Path] = None) -> str:
    """
    Creates a proto file with the given content in the specified workspace.
    
    Args:
        content: Proto file content
        filename: Name of the proto file
        workspace: Workspace directory (creates temp if None)
        
    Returns:
        Path to the created proto file
    """
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="proto_file_"))
    
    proto_path = workspace / filename
    proto_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(proto_path, "w") as f:
        f.write(content)
    
    return str(proto_path)


def create_test_buck_file(content: str, workspace: Path, subdir: str = "") -> str:
    """
    Creates a BUCK file with the given content.
    
    Args:
        content: BUCK file content
        workspace: Workspace directory
        subdir: Subdirectory within workspace
        
    Returns:
        Path to the created BUCK file
    """
    buck_dir = workspace / subdir if subdir else workspace
    buck_dir.mkdir(parents=True, exist_ok=True)
    
    buck_path = buck_dir / "BUCK"
    with open(buck_path, "w") as f:
        f.write(content)
    
    return str(buck_path)


def assert_files_exist(file_paths: List[str]) -> None:
    """
    Asserts that all specified files exist.
    
    Args:
        file_paths: List of file paths to check
        
    Raises:
        AssertionError: If any file doesn't exist
    """
    missing_files = []
    for file_path in file_paths:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        raise AssertionError(f"Files do not exist: {missing_files}")


def assert_files_not_exist(file_paths: List[str]) -> None:
    """
    Asserts that all specified files do not exist.
    
    Args:
        file_paths: List of file paths to check
        
    Raises:
        AssertionError: If any file exists
    """
    existing_files = []
    for file_path in file_paths:
        if os.path.exists(file_path):
            existing_files.append(file_path)
    
    if existing_files:
        raise AssertionError(f"Files should not exist: {existing_files}")


def assert_proto_compiles(proto_content: str, workspace: Optional[Path] = None) -> None:
    """
    Asserts that proto content compiles successfully using protoc.
    
    Args:
        proto_content: Proto file content to validate
        workspace: Workspace for temporary files
        
    Raises:
        AssertionError: If proto doesn't compile
    """
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="proto_compile_test_"))
    
    try:
        proto_file = create_test_proto_file(proto_content, "test.proto", workspace)
        
        # Run protoc to validate syntax
        result = run_command([
            "protoc",
            "--descriptor_set_out=/dev/null",
            "--proto_path=" + str(workspace),
            proto_file
        ])
        
        if result["exit_code"] != 0:
            raise AssertionError(f"Proto compilation failed: {result['stderr']}")
            
    finally:
        if workspace and workspace.exists():
            shutil.rmtree(workspace, ignore_errors=True)


def run_command(command: List[str], cwd: Optional[str] = None, timeout: float = 30.0) -> Dict[str, Union[str, int]]:
    """
    Runs a command and returns the result.
    
    Args:
        command: Command to run as list of arguments
        cwd: Working directory for the command
        timeout: Command timeout in seconds
        
    Returns:
        Dictionary with stdout, stderr, and exit_code
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "exit_code": 124,  # Standard timeout exit code
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": f"Command not found: {command[0]}",
            "exit_code": 127,  # Standard command not found exit code
        }


def run_buck2_command(command: List[str], cwd: Optional[str] = None, timeout: float = 60.0) -> Dict[str, Union[str, int]]:
    """
    Runs a Buck2 command and returns the result.
    
    Args:
        command: Buck2 command to run (without 'buck2' prefix)
        cwd: Working directory for the command
        timeout: Command timeout in seconds
        
    Returns:
        Dictionary with stdout, stderr, and exit_code
    """
    full_command = ["buck2"] + command
    return run_command(full_command, cwd=cwd, timeout=timeout)


def measure_performance(func, *args, **kwargs) -> Dict[str, Union[float, int]]:
    """
    Measures performance metrics for a function call.
    
    Args:
        func: Function to measure
        *args: Function arguments
        **kwargs: Function keyword arguments
        
    Returns:
        Dictionary with timing and memory metrics
    """
    # Measure memory before
    memory_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    
    # Measure execution time
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    
    # Measure memory after
    memory_after = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    
    return {
        "execution_time_ms": (end_time - start_time) * 1000,
        "memory_delta_kb": memory_after - memory_before,
        "result": result,
    }


def create_proto_with_deps(name: str, deps: List[str], workspace: Path) -> str:
    """
    Create a proto file that imports from dependencies.
    
    Args:
        name: Name of the proto file (without .proto extension)
        deps: List of proto files to import
        workspace: Workspace directory
        
    Returns:
        Path to the created proto file
    """
    imports = "\n".join([f'import "{dep}";' for dep in deps])
    
    content = f"""syntax = "proto3";

package test.{name};

{imports}

message {name.title()}Message {{
  int32 id = 1;
  string name = 2;
}}
"""
    
    return create_test_proto_file(content, f"{name}.proto", workspace)


def create_large_proto(num_fields: int = 100, workspace: Optional[Path] = None) -> str:
    """
    Create a large proto file for performance testing.
    
    Args:
        num_fields: Number of fields to include
        workspace: Workspace directory
        
    Returns:
        Path to the created proto file
    """
    if workspace is None:
        workspace = Path(tempfile.mkdtemp(prefix="large_proto_"))
    
    fields = []
    for i in range(num_fields):
        fields.append(f"  string field_{i} = {i + 1};")
    
    content = f"""syntax = "proto3";

package test.large;

message LargeMessage {{
{chr(10).join(fields)}
}}
"""
    
    return create_test_proto_file(content, "large.proto", workspace)


def validate_buck2_output(output: str, expected_patterns: List[str]) -> bool:
    """
    Validate that Buck2 output contains expected patterns.
    
    Args:
        output: Buck2 command output
        expected_patterns: List of patterns to match
        
    Returns:
        True if all patterns found
        
    Raises:
        AssertionError: If any pattern is missing
    """
    missing_patterns = []
    for pattern in expected_patterns:
        if pattern not in output:
            missing_patterns.append(pattern)
    
    if missing_patterns:
        raise AssertionError(f"Missing patterns in output: {missing_patterns}\nOutput: {output}")
    
    return True


def get_file_size(file_path: str) -> int:
    """Get file size in bytes."""
    return os.path.getsize(file_path) if os.path.exists(file_path) else 0


def wait_for_file(file_path: str, timeout: float = 5.0) -> bool:
    """
    Wait for a file to be created.
    
    Args:
        file_path: Path to file to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        True if file was created, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(file_path):
            return True
        time.sleep(0.1)
    return False


class TestTimer:
    """Context manager for timing test operations."""
    
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.perf_counter()
    
    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        if self.start_time is None or self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000


# Test data generators
def generate_test_protos(workspace: Path, count: int = 5) -> List[str]:
    """
    Generate multiple test proto files.
    
    Args:
        workspace: Workspace directory
        count: Number of proto files to generate
        
    Returns:
        List of created proto file paths
    """
    proto_files = []
    
    for i in range(count):
        content = f"""syntax = "proto3";

package test.proto{i};

message TestMessage{i} {{
  int32 id = 1;
  string name = 2;
  bool active = 3;
}}

enum TestEnum{i} {{
  UNKNOWN = 0;
  VALUE_{i} = {i + 1};
}}
"""
        proto_path = create_test_proto_file(content, f"test{i}.proto", workspace)
        proto_files.append(proto_path)
    
    return proto_files


if __name__ == "__main__":
    unittest.main()
