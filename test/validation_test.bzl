"""Comprehensive tests for protobuf validation and linting system."""

load("//rules:proto.bzl", "proto_library")
load("//rules:validation.bzl", "proto_validate", "proto_breaking_check", "custom_validation_rule")

def validation_test_suite():
    """Define comprehensive validation test suite."""
    
    # Test basic validation with buf lint
    test_buf_lint_validation()
    
    # Test breaking change detection
    test_breaking_change_detection()
    
    # Test custom validation rules
    test_custom_validation_rules()
    
    # Test malformed proto detection
    test_malformed_proto_validation()
    
    # Test performance with large schemas
    test_validation_performance()

def test_buf_lint_validation():
    """Test basic buf lint validation functionality."""
    
    # Create a proto library with good style
    proto_library(
        name = "good_style_proto",
        srcs = ["//test/fixtures/basic:minimal.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Validate the good proto
    proto_validate(
        name = "validate_good_style",
        srcs = [":good_style_proto"],
        linter = "buf",
        visibility = ["//test:__pkg__"],
    )
    
    # Create a proto library with style issues (for testing detection)
    proto_library(
        name = "style_issues_proto",
        srcs = ["//test/fixtures/edge_cases:malformed.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Validate the problematic proto (should catch issues)
    proto_validate(
        name = "validate_style_issues",
        srcs = [":style_issues_proto"],
        linter = "buf",
        visibility = ["//test:__pkg__"],
    )

def test_breaking_change_detection():
    """Test breaking change detection between proto versions."""
    
    # Create baseline proto
    proto_library(
        name = "baseline_proto",
        srcs = ["//test/fixtures/basic:types.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Create current proto (same as baseline for this test)
    proto_library(
        name = "current_proto",
        srcs = ["//test/fixtures/basic:types.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    # Check for breaking changes (should pass - no changes)
    proto_breaking_check(
        name = "check_no_breaking_changes",
        current = ":current_proto",
        baseline = ":baseline_proto",
        output_format = "json",
        visibility = ["//test:__pkg__"],
    )
    
    # Test with different files to simulate breaking changes
    proto_library(
        name = "modified_proto",
        srcs = ["//test/fixtures:complex.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_breaking_check(
        name = "check_with_changes", 
        current = ":modified_proto",
        baseline = ":baseline_proto",
        allow_breaking = True,  # Allow for testing
        output_format = "json",
        visibility = ["//test:__pkg__"],
    )

def test_custom_validation_rules():
    """Test custom validation rule system."""
    
    # Create custom validation rules
    custom_validation_rule(
        name = "check_package_naming",
        script = "//test/fixtures:check_package_naming.py",
        error_message = "Package names must follow organization standards",
        severity = "error",
        rule_name = "Package Naming Convention",
        description = "Ensures package names follow org.domain.service pattern",
        visibility = ["//test:__pkg__"],
    )
    
    custom_validation_rule(
        name = "check_service_naming",
        script = "//test/fixtures:check_service_naming.py", 
        error_message = "Service names must end with 'Service'",
        severity = "warning",
        rule_name = "Service Naming Convention",
        description = "Ensures all gRPC services follow naming conventions",
        visibility = ["//test:__pkg__"],
    )
    
    # Test proto with custom rules
    proto_library(
        name = "custom_rules_test_proto",
        srcs = ["//test/fixtures:service.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_validate(
        name = "validate_with_custom_rules",
        srcs = [":custom_rules_test_proto"],
        custom_rules = [
            ":check_package_naming",
            ":check_service_naming",
        ],
        visibility = ["//test:__pkg__"],
    )

def test_malformed_proto_validation():
    """Test validation of malformed protobuf files."""
    
    # Note: This would normally fail to build, but we test validation separately
    proto_validate(
        name = "validate_malformed_proto",
        srcs = ["//test/fixtures/edge_cases:malformed.proto"],
        linter = "buf",
        visibility = ["//test:__pkg__"],
    )

def test_validation_performance():
    """Test validation performance with large schemas."""
    
    proto_library(
        name = "large_proto",
        srcs = ["//test/fixtures/performance:large.proto"],
        visibility = ["//test:__pkg__"],
    )
    
    proto_validate(
        name = "validate_large_proto",
        srcs = [":large_proto"],
        linter = "buf",
        visibility = ["//test:__pkg__"],
    )

def test_comprehensive_validation():
    """Test comprehensive validation with all features enabled."""
    
    # Create baseline for breaking change detection
    proto_library(
        name = "comprehensive_baseline",
        srcs = [
            "//test/fixtures/basic:minimal.proto",
            "//test/fixtures/basic:types.proto",
        ],
        visibility = ["//test:__pkg__"],
    )
    
    # Create current version
    proto_library(
        name = "comprehensive_current",
        srcs = [
            "//test/fixtures/basic:minimal.proto",
            "//test/fixtures/basic:types.proto",
        ],
        visibility = ["//test:__pkg__"],
    )
    
    # Run comprehensive validation
    proto_validate(
        name = "comprehensive_validation",
        srcs = [":comprehensive_current"],
        linter = "buf",
        breaking_check = True,
        baseline = ":comprehensive_baseline",
        custom_rules = [
            ":check_package_naming",
            ":check_service_naming",
        ],
        visibility = ["//test:__pkg__"],
    )

# Legacy test cases for proto_library validation 
def test_empty_srcs():
    """Test case for validation - this should fail if we tried to build it."""
    proto_library(
        name = "empty_proto_test",
        srcs = [],  # This should fail validation
        visibility = ["//test:__pkg__"],
    )

def test_non_proto_file():
    """Test non-.proto file handling."""
    proto_library(
        name = "invalid_file_test", 
        srcs = ["test_data.json"],  # This should fail validation
        visibility = ["//test:__pkg__"],
    )
