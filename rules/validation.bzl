"""Validation and linting rules for protobuf schemas.

This module provides rules for validating protobuf schemas against linting rules
and conventions, as well as checking for breaking changes using Buf CLI and
custom validation rules.
"""

load("//rules/private:validation_impl.bzl", "proto_validate_impl", "proto_breaking_check_impl", "ValidationRuleInfo")
load("//rules/private:providers.bzl", "ValidationInfo")

# Rule for comprehensive protobuf validation
_proto_validate_rule = rule(
    implementation = proto_validate_impl,
    attrs = {
        "srcs": attr.label_list(
            mandatory = True,
            allow_files = [".proto"],
            doc = "List of .proto files or proto_library targets to validate",
        ),
        "linter": attr.string(
            default = "buf",
            values = ["buf", "protolint"],
            doc = "Linting tool to use",
        ),
        "breaking_check": attr.bool(
            default = False,
            doc = "Whether to check for breaking changes",
        ),
        "baseline": attr.label(
            allow_single_file = False,
            doc = "Baseline target for breaking change comparison",
        ),
        "custom_rules": attr.label_list(
            providers = [ValidationRuleInfo],
            doc = "List of custom validation rule targets",
        ),
        "config_file": attr.label(
            allow_single_file = True,
            doc = "Path to linter configuration file",
        ),
        "deps": attr.label_list(
            doc = "Proto library dependencies",
        ),
    },
    provides = [DefaultInfo, ValidationInfo],
    doc = "Validates protobuf schemas for style, consistency, and compatibility.",
)

# Rule for breaking change detection
_proto_breaking_check_rule = rule(
    implementation = proto_breaking_check_impl,
    attrs = {
        "current": attr.label(
            mandatory = True,
            doc = "Current proto_library target or proto files",
        ),
        "baseline": attr.label(
            mandatory = True,
            doc = "Baseline proto_library target",
        ),
        "allow_breaking": attr.bool(
            default = False,
            doc = "Whether breaking changes are allowed",
        ),
        "breaking_rules": attr.string_list(
            default = ["WIRE_COMPATIBLE"],
            doc = "List of breaking change rules to check",
        ),
        "output_format": attr.string(
            default = "text",
            values = ["text", "json", "github"],
            doc = "Output format for results",
        ),
    },
    provides = [DefaultInfo, ValidationInfo],
    doc = "Checks for breaking changes between protobuf schema versions.",
)

# Rule for custom validation rules
_custom_validation_rule = rule(
    implementation = lambda ctx: [
        DefaultInfo(files = depset([ctx.file.script])),
        ValidationRuleInfo(
            script = ctx.file.script,
            error_message = ctx.attr.error_message,
            severity = ctx.attr.severity,
            rule_name = ctx.attr.rule_name or ctx.label.name,
            description = ctx.attr.description,
        ),
    ],
    attrs = {
        "script": attr.label(
            mandatory = True,
            allow_single_file = True,
            executable = True,
            cfg = "exec",
            doc = "Executable script that implements the rule",
        ),
        "error_message": attr.string(
            mandatory = True,
            doc = "Error message to display on rule failure",
        ),
        "severity": attr.string(
            default = "error",
            values = ["error", "warning", "info"],
            doc = "Severity level",
        ),
        "rule_name": attr.string(
            doc = "Human-readable name of the rule",
        ),
        "description": attr.string(
            doc = "Description of what the rule validates",
        ),
    },
    provides = [DefaultInfo, ValidationRuleInfo],
    doc = "Define custom validation rules for organization standards.",
)

def proto_validate(
    name: str,
    srcs: list[str],
    linter: str = "buf",
    breaking_check: bool = False,
    baseline: str = "",
    custom_rules: list[str] = [],
    config_file: str = "",
    deps: list[str] = [],
    visibility: list[str] = None,
    **kwargs
):
    """
    Validates protobuf schemas for style, consistency, and compatibility.
    
    This rule runs comprehensive validation on protobuf schemas using Buf CLI,
    checks for breaking changes if requested, and executes custom validation rules.
    
    Args:
        name: Target name for the validation
        srcs: List of .proto files or proto_library targets to validate
        linter: Linting tool to use ("buf" or "protolint")
        breaking_check: Whether to check for breaking changes
        baseline: Baseline target for breaking change comparison
        custom_rules: List of custom validation rule targets
        config_file: Path to linter configuration file
        deps: Proto library dependencies
        visibility: Target visibility
        **kwargs: Additional arguments
    """
    _proto_validate_rule(
        name = name,
        srcs = srcs,
        linter = linter,
        breaking_check = breaking_check,
        baseline = baseline,
        custom_rules = custom_rules,
        config_file = config_file,
        deps = deps,
        visibility = visibility,
        **kwargs
    )

def proto_breaking_check(
    name: str,
    current: str,
    baseline: str,
    allow_breaking: bool = False,
    breaking_rules: list[str] = [],
    output_format: str = "text",
    visibility: list[str] = None,
    **kwargs
):
    """
    Checks for breaking changes between protobuf schema versions.
    
    This rule compares current protobuf schemas against a baseline to detect
    breaking changes that could impact API compatibility.
    
    Args:
        name: Target name for the breaking change check
        current: Current proto_library target or proto files
        baseline: Baseline proto_library target
        allow_breaking: Whether breaking changes are allowed
        breaking_rules: List of breaking change rules to check
        output_format: Output format ("text", "json", "github")
        visibility: Target visibility
        **kwargs: Additional arguments
    """
    _proto_breaking_check_rule(
        name = name,
        current = current,
        baseline = baseline,
        allow_breaking = allow_breaking,
        breaking_rules = breaking_rules,
        output_format = output_format,
        visibility = visibility,
        **kwargs
    )

def custom_validation_rule(
    name: str,
    script: str,
    error_message: str,
    severity: str = "error",
    rule_name: str = "",
    description: str = "",
    visibility: list[str] = None,
    **kwargs
):
    """
    Define custom validation rules for organization standards.
    
    This rule creates a custom validation rule that can be executed as part
    of proto_validate to enforce organization-specific protobuf standards.
    
    Args:
        name: Target name for the custom rule
        script: Executable script that implements the rule
        error_message: Error message to display on rule failure
        severity: Severity level ("error", "warning", "info")
        rule_name: Human-readable name of the rule
        description: Description of what the rule validates
        visibility: Target visibility
        **kwargs: Additional arguments
    """
    _custom_validation_rule(
        name = name,
        script = script,
        error_message = error_message,
        severity = severity,
        rule_name = rule_name,
        description = description,
        visibility = visibility,
        **kwargs
    )
