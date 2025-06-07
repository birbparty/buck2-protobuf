"""Implementation of protobuf validation and linting functionality.

This module provides the core implementation for proto validation using Buf CLI,
breaking change detection, and custom validation rules.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "ValidationInfo")
load("//rules/private:utils.bzl", "merge_proto_infos")

def _get_buf_binary(ctx):
    """Get the Buf CLI binary for the current platform."""
    # For now, we'll use a downloaded buf binary from tools directory
    # In production, this would be dynamically downloaded based on platform
    buf_binary = ctx.actions.declare_output("buf")
    
    # Create a simple script that downloads buf if needed
    download_script = ctx.actions.write(
        "download_buf.sh",
        content = """#!/bin/bash
set -euo pipefail

TOOLS_DIR="$(dirname "$0")/../../../tools"
BUF_PATH="$TOOLS_DIR/buf"

# Download buf if it doesn't exist or is invalid
if [ ! -f "$BUF_PATH" ] || ! "$BUF_PATH" --version >/dev/null 2>&1; then
    echo "Downloading Buf CLI..." >&2
    python3 "$TOOLS_DIR/download_buf.py" --output-dir "$TOOLS_DIR" --verbose
fi

# Copy to output location
cp "$BUF_PATH" "$1"
chmod +x "$1"
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [download_script],
        outputs = [buf_binary],
        arguments = [buf_binary.as_output()],
        executable = download_script,
    )
    
    return buf_binary

def _create_buf_config(ctx, lint_rules = None, breaking_rules = None):
    """Create a buf.yaml configuration file."""
    config_content = """version: v1
lint:
  use:
"""
    
    # Default lint rules
    default_lint_rules = [
        "DEFAULT",
        "FIELD_NAMES_LOWER_SNAKE_CASE", 
        "SERVICE_NAMES_PASCAL_CASE",
        "ENUM_NAMES_UPPER_SNAKE_CASE",
    ]
    
    rules_to_use = lint_rules if lint_rules else default_lint_rules
    for rule in rules_to_use:
        config_content += f"    - {rule}\n"
    
    # Add breaking change configuration if specified
    if breaking_rules:
        config_content += "breaking:\n  use:\n"
        for rule in breaking_rules:
            config_content += f"    - {rule}\n"
    else:
        config_content += """breaking:
  use:
    - WIRE_COMPATIBLE
"""
    
    config_file = ctx.actions.declare_output("buf.yaml")
    ctx.actions.write(config_file, config_content)
    return config_file

def _create_buf_work_yaml(ctx, proto_files):
    """Create a buf.work.yaml file for workspace management."""
    # Create a workspace configuration that includes all proto directories
    directories = {}
    for proto_file in proto_files:
        # Get the directory containing the proto file
        proto_dir = proto_file.dirname
        if proto_dir and proto_dir != ".":
            directories[proto_dir] = True
        else:
            directories["."] = True
    
    work_content = "version: v1\ndirectories:\n"
    for directory in sorted(directories.keys()):
        work_content += f"  - {directory}\n"
    
    work_file = ctx.actions.declare_output("buf.work.yaml")
    ctx.actions.write(work_file, work_content)
    return work_file

def _run_buf_lint(ctx, buf_binary, config_file, proto_files, import_paths):
    """Execute buf lint on proto files."""
    output_file = ctx.actions.declare_output("lint_results.json")
    
    # Create a directory structure for buf to work with
    proto_root = ctx.actions.declare_output("proto_root", dir = True)
    
    # Copy proto files to the root directory structure
    copied_files = []
    for proto_file in proto_files:
        # Maintain directory structure
        relative_path = proto_file.short_path
        if relative_path.startswith("../"):
            relative_path = relative_path[3:]  # Remove ../ prefix
        
        copied_file = ctx.actions.declare_output(f"proto_root/{relative_path}")
        ctx.actions.copy_file(proto_file, copied_file)
        copied_files.append(copied_file)
    
    # Copy config file to proto root
    root_config = ctx.actions.declare_output("proto_root/buf.yaml")
    ctx.actions.copy_file(config_file, root_config)
    
    # Create lint script
    lint_script = ctx.actions.write(
        "run_lint.sh",
        content = f"""#!/bin/bash
set -euo pipefail

BUF_BINARY="$1"
PROTO_ROOT="$2"
OUTPUT_FILE="$3"

cd "$PROTO_ROOT"

# Run buf lint with JSON output
if "$BUF_BINARY" lint --error-format json > "$OUTPUT_FILE" 2>&1; then
    echo "Lint passed" >&2
    exit 0
else
    echo "Lint found issues, check $OUTPUT_FILE" >&2
    exit 1
fi
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [buf_binary, proto_root, config_file] + copied_files,
        outputs = [output_file],
        arguments = [
            buf_binary.as_output(),
            proto_root.as_output(),
            output_file.as_output(),
        ],
        executable = lint_script,
        env = {
            "BUF_CACHE_DIR": "/tmp/buf-cache",
        },
    )
    
    return output_file

def _run_buf_breaking(ctx, buf_binary, config_file, current_files, baseline_files):
    """Execute buf breaking change detection."""
    output_file = ctx.actions.declare_output("breaking_results.json")
    
    # Create current and baseline directory structures
    current_root = ctx.actions.declare_output("current_root", dir = True)
    baseline_root = ctx.actions.declare_output("baseline_root", dir = True)
    
    # Copy current files
    for proto_file in current_files:
        relative_path = proto_file.short_path
        if relative_path.startswith("../"):
            relative_path = relative_path[3:]
        
        copied_file = ctx.actions.declare_output(f"current_root/{relative_path}")
        ctx.actions.copy_file(proto_file, copied_file)
    
    # Copy baseline files
    for proto_file in baseline_files:
        relative_path = proto_file.short_path
        if relative_path.startswith("../"):
            relative_path = relative_path[3:]
        
        copied_file = ctx.actions.declare_output(f"baseline_root/{relative_path}")
        ctx.actions.copy_file(proto_file, copied_file)
    
    # Copy config to both roots
    current_config = ctx.actions.declare_output("current_root/buf.yaml")
    baseline_config = ctx.actions.declare_output("baseline_root/buf.yaml")
    ctx.actions.copy_file(config_file, current_config)
    ctx.actions.copy_file(config_file, baseline_config)
    
    # Create breaking change detection script
    breaking_script = ctx.actions.write(
        "run_breaking.sh",
        content = f"""#!/bin/bash
set -euo pipefail

BUF_BINARY="$1"
CURRENT_ROOT="$2"
BASELINE_ROOT="$3"
OUTPUT_FILE="$4"

cd "$CURRENT_ROOT"

# Run buf breaking change detection
if "$BUF_BINARY" breaking --against "$BASELINE_ROOT" --error-format json > "$OUTPUT_FILE" 2>&1; then
    echo "No breaking changes detected" >&2
    exit 0
else
    echo "Breaking changes detected, check $OUTPUT_FILE" >&2
    exit 1
fi
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [buf_binary, current_root, baseline_root, config_file],
        outputs = [output_file],
        arguments = [
            buf_binary.as_output(),
            current_root.as_output(),
            baseline_root.as_output(),
            output_file.as_output(),
        ],
        executable = breaking_script,
        env = {
            "BUF_CACHE_DIR": "/tmp/buf-cache",
        },
    )
    
    return output_file

def _execute_custom_rules(ctx, proto_files, custom_rules):
    """Execute custom validation rules."""
    results = []
    
    for rule in custom_rules:
        # Each custom rule should provide a ValidationRuleInfo provider
        rule_info = rule[ValidationRuleInfo] if ValidationRuleInfo in rule else None
        if not rule_info:
            continue
        
        result_file = ctx.actions.declare_output(f"custom_rule_{rule.label.name}_result.json")
        
        # Create execution script for the custom rule
        exec_script = ctx.actions.write(
            f"exec_rule_{rule.label.name}.sh",
            content = f"""#!/bin/bash
set -euo pipefail

RULE_SCRIPT="$1"
OUTPUT_FILE="$2"
shift 2

# Execute the custom rule script with proto files as arguments
if "$RULE_SCRIPT" "$@" > "$OUTPUT_FILE" 2>&1; then
    echo "Custom rule passed: {rule.label.name}" >&2
    exit 0
else
    echo "Custom rule failed: {rule.label.name}" >&2
    exit 1
fi
""",
            is_executable = True,
        )
        
        # Run the custom rule
        proto_file_args = [f.as_output() for f in proto_files]
        ctx.actions.run(
            inputs = [rule_info.script] + proto_files,
            outputs = [result_file],
            arguments = [rule_info.script.as_output(), result_file.as_output()] + proto_file_args,
            executable = exec_script,
        )
        
        results.append(result_file)
    
    return results

def _create_validation_report(ctx, lint_result, breaking_result, custom_results, output_format):
    """Create a comprehensive validation report."""
    report_file = ctx.actions.declare_output(f"validation_report.{output_format}")
    
    # Create report generation script
    report_script = ctx.actions.write(
        "create_report.py",
        content = f"""#!/usr/bin/env python3
import json
import sys
from pathlib import Path

def load_json_file(filepath):
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return {{"error": f"Failed to load {{filepath}}"}}

def create_text_report(lint_data, breaking_data, custom_data):
    report = "PROTOBUF VALIDATION REPORT\\n"
    report += "=" * 50 + "\\n\\n"
    
    # Lint results
    report += "LINTING RESULTS:\\n"
    if isinstance(lint_data, dict) and "error" not in lint_data:
        report += "✓ All linting checks passed\\n"
    else:
        report += "✗ Linting issues found\\n"
        if isinstance(lint_data, dict):
            report += f"Details: {{lint_data}}\\n"
    
    report += "\\n"
    
    # Breaking changes
    report += "BREAKING CHANGE DETECTION:\\n"
    if isinstance(breaking_data, dict) and "error" not in breaking_data:
        report += "✓ No breaking changes detected\\n"
    else:
        report += "✗ Breaking changes detected\\n"
        if isinstance(breaking_data, dict):
            report += f"Details: {{breaking_data}}\\n"
    
    report += "\\n"
    
    # Custom rules
    report += "CUSTOM VALIDATION RULES:\\n"
    if custom_data:
        for i, result in enumerate(custom_data):
            report += f"Rule {{i+1}}: {{'✓' if 'error' not in result else '✗'}}\\n"
    else:
        report += "No custom rules executed\\n"
    
    return report

def create_json_report(lint_data, breaking_data, custom_data):
    return json.dumps({{
        "validation_summary": {{
            "lint_passed": isinstance(lint_data, dict) and "error" not in lint_data,
            "breaking_changes": isinstance(breaking_data, dict) and "error" in breaking_data,
            "custom_rules_passed": all("error" not in r for r in custom_data) if custom_data else True,
        }},
        "lint_results": lint_data,
        "breaking_results": breaking_data,
        "custom_results": custom_data,
    }}, indent=2)

def main():
    lint_file = sys.argv[1]
    breaking_file = sys.argv[2]
    output_file = sys.argv[3]
    output_format = sys.argv[4]
    custom_files = sys.argv[5:] if len(sys.argv) > 5 else []
    
    lint_data = load_json_file(lint_file)
    breaking_data = load_json_file(breaking_file)
    custom_data = [load_json_file(f) for f in custom_files]
    
    if output_format == "json":
        content = create_json_report(lint_data, breaking_data, custom_data)
    else:
        content = create_text_report(lint_data, breaking_data, custom_data)
    
    with open(output_file, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    main()
""",
        is_executable = True,
    )
    
    # Prepare arguments
    args = [
        lint_result.as_output() if lint_result else "/dev/null",
        breaking_result.as_output() if breaking_result else "/dev/null", 
        report_file.as_output(),
        output_format,
    ]
    
    if custom_results:
        args.extend([r.as_output() for r in custom_results])
    
    # Create the report
    inputs = [report_script]
    if lint_result:
        inputs.append(lint_result)
    if breaking_result:
        inputs.append(breaking_result)
    if custom_results:
        inputs.extend(custom_results)
    
    ctx.actions.run(
        inputs = inputs,
        outputs = [report_file],
        arguments = args,
        executable = report_script,
    )
    
    return report_file

def proto_validate_impl(ctx):
    """Implementation of proto_validate rule."""
    # Get proto files from srcs
    proto_files = []
    proto_infos = []
    
    for src in ctx.attrs.srcs:
        if ProtoInfo in src:
            proto_infos.append(src[ProtoInfo])
            proto_files.extend(src[ProtoInfo].proto_files)
        else:
            # Direct proto file
            proto_files.append(src)
    
    # Merge dependency proto info
    merged_info = merge_proto_infos(proto_infos)
    all_proto_files = proto_files + merged_info.get("transitive_proto_files", [])
    import_paths = merged_info.get("transitive_import_paths", [])
    
    # Get tools and configuration
    buf_binary = _get_buf_binary(ctx)
    
    # Determine configuration
    if ctx.attrs.config_file:
        config_file = ctx.attrs.config_file
    else:
        # Create default configuration
        config_file = _create_buf_config(ctx)
    
    # Run linting
    lint_result = None
    if ctx.attrs.linter == "buf":
        lint_result = _run_buf_lint(ctx, buf_binary, config_file, all_proto_files, import_paths)
    
    # Run breaking change detection if requested
    breaking_result = None
    if ctx.attrs.breaking_check and ctx.attrs.baseline:
        # For now, use the same files as baseline (this would be enhanced in production)
        baseline_files = all_proto_files  # TODO: Get actual baseline files
        breaking_result = _run_buf_breaking(ctx, buf_binary, config_file, all_proto_files, baseline_files)
    
    # Execute custom validation rules
    custom_results = []
    if ctx.attrs.custom_rules:
        custom_results = _execute_custom_rules(ctx, all_proto_files, ctx.attrs.custom_rules)
    
    # Create comprehensive report
    report = _create_validation_report(
        ctx,
        lint_result,
        breaking_result,
        custom_results,
        "json"  # Default format
    )
    
    # Create validation info provider
    validation_info = ValidationInfo(
        passed = True,  # Would be determined by actual results
        lint_result = lint_result,
        breaking_result = breaking_result,
        custom_results = custom_results,
        report = report,
    )
    
    return [
        DefaultInfo(files = depset([report])),
        validation_info,
    ]

def proto_breaking_check_impl(ctx):
    """Implementation of proto_breaking_check rule."""
    # Get current and baseline proto files
    current_files = []
    baseline_files = []
    
    # Process current files
    if hasattr(ctx.attrs.current, "files"):
        current_files = ctx.attrs.current.files.to_list()
    elif ProtoInfo in ctx.attrs.current:
        current_files = ctx.attrs.current[ProtoInfo].proto_files
    
    # Process baseline files  
    if hasattr(ctx.attrs.baseline, "files"):
        baseline_files = ctx.attrs.baseline.files.to_list()
    elif ProtoInfo in ctx.attrs.baseline:
        baseline_files = ctx.attrs.baseline[ProtoInfo].proto_files
    
    # Get tools and configuration
    buf_binary = _get_buf_binary(ctx)
    config_file = _create_buf_config(ctx, breaking_rules = ctx.attrs.breaking_rules)
    
    # Run breaking change detection
    breaking_result = _run_buf_breaking(ctx, buf_binary, config_file, current_files, baseline_files)
    
    # Create report in requested format
    report = _create_validation_report(
        ctx,
        None,  # No lint result
        breaking_result,
        [],  # No custom results
        ctx.attrs.output_format
    )
    
    return [
        DefaultInfo(files = depset([report])),
        ValidationInfo(
            passed = True,  # Would be determined by actual results
            breaking_result = breaking_result,
            report = report,
        ),
    ]

# Define ValidationRuleInfo provider for custom rules
ValidationRuleInfo = provider(
    doc = "Information about a custom validation rule.",
    fields = {
        "script": "Executable script that implements the rule",
        "error_message": "Error message to display on rule failure",
        "severity": "Severity level (error, warning, info)",
    },
)
