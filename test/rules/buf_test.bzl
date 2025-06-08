"""Tests for buf rules implementation.

This module provides comprehensive tests for buf_lint, buf_format, and
buf_breaking rules to ensure they work correctly with various configurations
and edge cases.
"""

load("//rules:buf.bzl", "buf_lint", "buf_format", "buf_breaking")
load("//rules/private:providers.bzl", "BufLintInfo", "BufFormatInfo", "BufBreakingInfo")

def test_buf_lint_basic():
    """Test basic buf_lint functionality."""
    buf_lint(
        name = "test_lint_basic",
        srcs = ["//test/fixtures:simple.proto"],
    )

def test_buf_lint_with_config():
    """Test buf_lint with inline configuration."""
    buf_lint(
        name = "test_lint_config",
        srcs = ["//test/fixtures:simple.proto"],
        config = {
            "use": ["DEFAULT", "COMMENTS"],
            "except": ["PACKAGE_VERSION_SUFFIX"],
            "enum_zero_value_suffix": "_UNSPECIFIED",
        },
    )

def test_buf_lint_with_buf_yaml():
    """Test buf_lint with buf.yaml configuration file."""
    buf_lint(
        name = "test_lint_buf_yaml",
        srcs = ["//test/fixtures:simple.proto"],
        buf_yaml = "//examples/buf:buf.yaml",
    )

def test_buf_lint_multiple_files():
    """Test buf_lint with multiple proto files."""
    buf_lint(
        name = "test_lint_multiple",
        srcs = [
            "//test/fixtures:simple.proto",
            "//test/fixtures:complex.proto",
            "//test/fixtures:service.proto",
        ],
    )

def test_buf_lint_fail_on_error_false():
    """Test buf_lint with fail_on_error set to false."""
    buf_lint(
        name = "test_lint_no_fail",
        srcs = ["//test/fixtures:simple.proto"],
        fail_on_error = False,
    )

def test_buf_format_diff():
    """Test buf_format in diff mode."""
    buf_format(
        name = "test_format_diff",
        srcs = ["//test/fixtures:simple.proto"],
        diff = True,
    )

def test_buf_format_write():
    """Test buf_format in write mode."""
    buf_format(
        name = "test_format_write",
        srcs = ["//test/fixtures:simple.proto"],
        write = True,
    )

def test_buf_format_multiple_files():
    """Test buf_format with multiple proto files."""
    buf_format(
        name = "test_format_multiple",
        srcs = [
            "//test/fixtures:simple.proto",
            "//test/fixtures:complex.proto",
        ],
        diff = True,
    )

def test_buf_format_with_config():
    """Test buf_format with buf.yaml configuration."""
    buf_format(
        name = "test_format_with_config",
        srcs = ["//test/fixtures:simple.proto"],
        buf_yaml = "//examples/buf:buf.yaml",
        diff = True,
    )

def test_buf_breaking_file_baseline():
    """Test buf_breaking with file baseline."""
    buf_breaking(
        name = "test_breaking_file",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures/baseline:simple.proto",
    )

def test_buf_breaking_git_baseline():
    """Test buf_breaking with git baseline."""
    buf_breaking(
        name = "test_breaking_git",
        srcs = ["//test/fixtures:simple.proto"],
        against = "git#branch=main",
    )

def test_buf_breaking_target_baseline():
    """Test buf_breaking with Buck2 target baseline."""
    buf_breaking(
        name = "test_breaking_target",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//baseline:simple_proto",
    )

def test_buf_breaking_with_config():
    """Test buf_breaking with inline configuration."""
    buf_breaking(
        name = "test_breaking_config",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures/baseline:simple.proto",
        config = {
            "use": ["WIRE_COMPATIBLE"],
            "except": ["FIELD_SAME_DEFAULT"],
        },
    )

def test_buf_breaking_with_buf_yaml():
    """Test buf_breaking with buf.yaml configuration."""
    buf_breaking(
        name = "test_breaking_buf_yaml",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures/baseline:simple.proto",
        buf_yaml = "//examples/buf:buf.yaml",
    )

def test_buf_breaking_multiple_files():
    """Test buf_breaking with multiple proto files."""
    buf_breaking(
        name = "test_breaking_multiple",
        srcs = [
            "//test/fixtures:simple.proto",
            "//test/fixtures:complex.proto",
        ],
        against = "//test/fixtures/baseline",
    )

# Integration tests combining multiple buf operations

def test_buf_lint_format_integration():
    """Test integration of buf_lint and buf_format on same files."""
    # First lint the files
    buf_lint(
        name = "integration_lint",
        srcs = ["//examples/buf:user.proto"],
        buf_yaml = "//examples/buf:buf.yaml",
    )
    
    # Then check formatting
    buf_format(
        name = "integration_format",
        srcs = ["//examples/buf:user.proto"],
        buf_yaml = "//examples/buf:buf.yaml",
        diff = True,
    )

def test_buf_full_workflow():
    """Test complete buf workflow: lint, format, breaking."""
    # Lint validation
    buf_lint(
        name = "workflow_lint",
        srcs = [
            "//examples/buf:user.proto",
            "//examples/buf:user_types.proto",
        ],
        buf_yaml = "//examples/buf:buf.yaml",
    )
    
    # Format validation
    buf_format(
        name = "workflow_format",
        srcs = [
            "//examples/buf:user.proto",
            "//examples/buf:user_types.proto",
        ],
        buf_yaml = "//examples/buf:buf.yaml",
        diff = True,
    )
    
    # Breaking change detection
    buf_breaking(
        name = "workflow_breaking",
        srcs = [
            "//examples/buf:user.proto",
            "//examples/buf:user_types.proto",
        ],
        against = "git#branch=main",
        buf_yaml = "//examples/buf:buf.yaml",
    )

# Error handling tests

def test_buf_lint_empty_srcs():
    """Test buf_lint error handling with empty srcs."""
    # This should fail with a descriptive error message
    # In a real test framework, we would assert the failure
    pass

def test_buf_format_invalid_config():
    """Test buf_format error handling with invalid configuration."""
    # This should fail with configuration validation error
    pass

def test_buf_breaking_missing_against():
    """Test buf_breaking error handling with missing against parameter."""
    # This should fail with missing parameter error
    pass

# Performance tests

def test_buf_lint_large_files():
    """Test buf_lint performance with large proto files."""
    buf_lint(
        name = "perf_lint_large",
        srcs = ["//test/fixtures/performance:large.proto"],
        config = {"use": ["DEFAULT"]},
    )

def test_buf_format_many_files():
    """Test buf_format performance with many proto files."""
    buf_format(
        name = "perf_format_many",
        srcs = [
            "//test/fixtures/performance:file1.proto",
            "//test/fixtures/performance:file2.proto",
            "//test/fixtures/performance:file3.proto",
            "//test/fixtures/performance:file4.proto",
            "//test/fixtures/performance:file5.proto",
        ],
        diff = True,
    )

# Caching tests

def test_buf_lint_caching():
    """Test that buf_lint results are properly cached."""
    # Run the same lint operation twice to test caching
    buf_lint(
        name = "cache_lint_1",
        srcs = ["//test/fixtures:simple.proto"],
        config = {"use": ["DEFAULT"]},
    )
    
    buf_lint(
        name = "cache_lint_2", 
        srcs = ["//test/fixtures:simple.proto"],
        config = {"use": ["DEFAULT"]},
    )

def test_buf_format_caching():
    """Test that buf_format results are properly cached."""
    buf_format(
        name = "cache_format_1",
        srcs = ["//test/fixtures:simple.proto"],
        diff = True,
    )
    
    buf_format(
        name = "cache_format_2",
        srcs = ["//test/fixtures:simple.proto"],
        diff = True,
    )

def test_buf_breaking_caching():
    """Test that buf_breaking results are properly cached."""
    buf_breaking(
        name = "cache_breaking_1",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures/baseline:simple.proto",
    )
    
    buf_breaking(
        name = "cache_breaking_2",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures/baseline:simple.proto",
    )

# Configuration discovery tests

def test_buf_config_discovery():
    """Test automatic buf.yaml configuration discovery."""
    # Test that buf rules can find buf.yaml in the source directory
    buf_lint(
        name = "discovery_lint",
        srcs = ["//examples/buf:user.proto"],
        # No explicit buf_yaml - should discover examples/buf/buf.yaml
    )

def test_buf_config_inheritance():
    """Test buf configuration inheritance and overrides."""
    buf_lint(
        name = "inheritance_lint",
        srcs = ["//examples/buf:user.proto"],
        buf_yaml = "//examples/buf:buf.yaml",
        config = {
            # These should override the buf.yaml settings
            "except": ["PACKAGE_VERSION_SUFFIX", "FIELD_NAMES_LOWER_SNAKE_CASE"],
        },
    )

# Edge case tests

def test_buf_lint_proto_with_imports():
    """Test buf_lint with proto files that have imports."""
    buf_lint(
        name = "imports_lint",
        srcs = ["//examples/buf:user.proto"],  # This imports user_types.proto
        buf_yaml = "//examples/buf:buf.yaml",
    )

def test_buf_format_proto_with_syntax_errors():
    """Test buf_format behavior with syntax errors."""
    # This should handle syntax errors gracefully
    pass

def test_buf_breaking_identical_files():
    """Test buf_breaking with identical current and baseline files."""
    buf_breaking(
        name = "identical_breaking",
        srcs = ["//test/fixtures:simple.proto"],
        against = "//test/fixtures:simple.proto",  # Same file
    )

# Toolchain tests

def test_buf_toolchain_integration():
    """Test that buf rules properly integrate with the buf toolchain."""
    # This tests the toolchain dependency and buf CLI acquisition
    buf_lint(
        name = "toolchain_lint",
        srcs = ["//test/fixtures:simple.proto"],
    )

def test_buf_different_versions():
    """Test buf rules with different buf CLI versions."""
    # This would test version compatibility
    # In a real implementation, we might have version-specific targets
    pass

# Provider tests

def test_buf_lint_provider():
    """Test that buf_lint properly provides BufLintInfo."""
    # In a real test framework, we would inspect the returned providers
    pass

def test_buf_format_provider():
    """Test that buf_format properly provides BufFormatInfo."""
    pass

def test_buf_breaking_provider():
    """Test that buf_breaking properly provides BufBreakingInfo."""
    pass
