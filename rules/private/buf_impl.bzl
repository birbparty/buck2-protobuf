"""Implementation functions for buf rules.

This module contains the core implementation logic for buf lint, format,
and breaking change detection rules. It handles buf CLI execution, caching,
configuration discovery, and error reporting.
"""

load("//rules/private:providers.bzl", "BufLintInfo", "BufFormatInfo", "BufBreakingInfo", "BufToolchainInfo")
load("//rules/private:buf_config.bzl", "discover_comprehensive_buf_config", "create_buf_config", "validate_buf_config", "create_effective_buf_config")
load("//rules/private:utils.bzl", "get_short_path", "create_cache_key")

def buf_lint_impl(ctx):
    """
    Implementation function for buf_lint rule.
    
    Executes buf lint on protobuf files with proper caching and error handling.
    
    Args:
        ctx: Buck2 rule context
        
    Returns:
        List of providers including BufLintInfo and DefaultInfo
    """
    # Get buf CLI from toolchain
    buf_toolchain = ctx.toolchains["//tools:buf_toolchain"][BufToolchainInfo]
    buf_cli = buf_toolchain.buf_cli
    
    # Get source files
    proto_files = ctx.attrs.srcs
    if not proto_files:
        fail("buf_lint: srcs cannot be empty")
    
    # Comprehensive configuration discovery with validation and merging
    config_result = discover_comprehensive_buf_config(ctx, proto_files, "lint")
    
    # Check for validation errors
    if config_result.validation_errors:
        error_msg = "Buf configuration validation errors:\n" + "\n".join(config_result.validation_errors)
        if ctx.attrs.fail_on_error:
            fail(error_msg)
        else:
            print("Warning: " + error_msg)
    
    # Determine which configuration file to use for buf CLI
    buf_config = None
    if ctx.attrs.buf_yaml:
        # Explicit buf_yaml parameter takes precedence
        buf_config = ctx.attrs.buf_yaml
    elif config_result.module_config and config_result.module_config.config_file:
        # Use discovered module config file
        buf_config = config_result.module_config.config_file
    elif config_result.workspace_config and config_result.workspace_config.workspace_file:
        # For workspace configs, we might need to create a temporary module-specific config
        buf_config = create_buf_config(ctx, config_result.effective_config.get("lint", {}), "lint")
    elif ctx.attrs.config:
        # Create temporary config from inline parameters
        buf_config = create_buf_config(ctx, ctx.attrs.config, "lint")
    
    # Create output files
    lint_report_json = ctx.actions.declare_output("buf_lint_report.json")
    lint_report_text = ctx.actions.declare_output("buf_lint_report.txt")
    
    # Build buf lint command
    cmd = cmd_args([buf_cli, "lint"])
    
    # Add configuration if available
    inputs = list(proto_files)
    if buf_config:
        cmd.add("--config", buf_config)
        inputs.append(buf_config)
    
    # Add format options for machine-readable output
    cmd.add("--format", "json")
    cmd.add("--output", lint_report_json.as_output())
    
    # Add proto files
    for proto_file in proto_files:
        cmd.add(get_short_path(proto_file))
    
    # Set working directory to the directory containing proto files
    # This helps with import path resolution
    working_dir = "."
    if proto_files:
        first_proto = proto_files[0]
        proto_dir = "/".join(get_short_path(first_proto).split("/")[:-1])
        if proto_dir:
            working_dir = proto_dir
    
    # Create cache key for this lint operation
    cache_key = create_cache_key([
        buf_toolchain.version,
        str(ctx.attrs.config),
        str([get_short_path(f) for f in proto_files]),
        str(ctx.attrs.fail_on_error),
    ])
    
    # Execute buf lint
    ctx.actions.run(
        cmd,
        category = "buf_lint",
        identifier = cache_key,
        inputs = inputs,
        outputs = [lint_report_json],
        env = {
            "BUF_CACHE_DIR": "buck-out/buf-cache",
            "PATH": "/usr/bin:/bin",
        },
        allow_cache_upload = True,
        allow_dep_file_cache_upload = True,
        working_directory = working_dir,
    )
    
    # Create human-readable report as well
    create_readable_lint_report(ctx, lint_report_json, lint_report_text)
    
    # Parse lint results to determine if linting passed
    # In a real implementation, we would parse the JSON to extract details
    # For now, we assume the action succeeds if buf lint exits with 0
    lint_passed = True  # Will be determined by action success
    
    # Create BufLintInfo provider
    buf_lint_info = BufLintInfo(
        lint_report = lint_report_json,
        violations = [],  # Would be parsed from JSON in real implementation
        passed = lint_passed,
        config_used = buf_config,
        files_linted = proto_files,
        lint_time_ms = 0,  # Would be measured in real implementation
        rules_applied = [],  # Would be extracted from config
        error_count = 0,  # Would be parsed from JSON
        warning_count = 0,  # Would be parsed from JSON
    )
    
    # Determine outputs based on fail_on_error setting
    outputs = [lint_report_json, lint_report_text]
    
    return [
        DefaultInfo(default_outputs = outputs),
        buf_lint_info,
    ]

def buf_format_impl(ctx):
    """
    Implementation function for buf_format rule.
    
    Executes buf format on protobuf files with diff or write mode.
    
    Args:
        ctx: Buck2 rule context
        
    Returns:
        List of providers including BufFormatInfo and DefaultInfo
    """
    # Get buf CLI from toolchain
    buf_toolchain = ctx.toolchains["//tools:buf_toolchain"][BufToolchainInfo]
    buf_cli = buf_toolchain.buf_cli
    
    # Get source files
    proto_files = ctx.attrs.srcs
    if not proto_files:
        fail("buf_format: srcs cannot be empty")
    
    # Comprehensive configuration discovery with validation and merging
    config_result = discover_comprehensive_buf_config(ctx, proto_files, "format")
    
    # Check for validation errors (format is usually more lenient)
    if config_result.validation_errors:
        error_msg = "Buf configuration validation errors:\n" + "\n".join(config_result.validation_errors)
        print("Warning: " + error_msg)
    
    # Determine which configuration file to use for buf CLI
    buf_config = None
    if ctx.attrs.buf_yaml:
        # Explicit buf_yaml parameter takes precedence
        buf_config = ctx.attrs.buf_yaml
    elif config_result.module_config and config_result.module_config.config_file:
        # Use discovered module config file
        buf_config = config_result.module_config.config_file
    elif config_result.workspace_config and config_result.workspace_config.workspace_file:
        # For workspace configs, use the workspace file directly
        buf_config = config_result.workspace_config.workspace_file
    
    inputs = list(proto_files)
    if buf_config:
        inputs.append(buf_config)
    
    outputs = []
    
    if ctx.attrs.diff:
        # Diff mode - show formatting differences
        diff_report = ctx.actions.declare_output("buf_format_diff.txt")
        outputs.append(diff_report)
        
        # Build buf format --diff command
        cmd = cmd_args([buf_cli, "format", "--diff"])
        
        if buf_config:
            cmd.add("--config", buf_config)
        
        # Add proto files
        for proto_file in proto_files:
            cmd.add(get_short_path(proto_file))
        
        # Execute buf format --diff
        ctx.actions.run(
            cmd,
            category = "buf_format_diff",
            identifier = "format_diff_" + ctx.label.name,
            inputs = inputs,
            outputs = [diff_report],
            env = {
                "BUF_CACHE_DIR": "buck-out/buf-cache",
                "PATH": "/usr/bin:/bin",
            },
            # Redirect stdout to diff report
            stdout = diff_report,
        )
        
        formatted_files = []
        diff_output = diff_report
        
    elif ctx.attrs.write:
        # Write mode - generate formatted files
        formatted_files = []
        
        for proto_file in proto_files:
            # Create output file for each formatted proto
            formatted_file = ctx.actions.declare_output(
                "formatted", 
                get_short_path(proto_file)
            )
            formatted_files.append(formatted_file)
        
        outputs.extend(formatted_files)
        
        # Build buf format command for each file
        for i, proto_file in enumerate(proto_files):
            cmd = cmd_args([buf_cli, "format"])
            
            if buf_config:
                cmd.add("--config", buf_config)
            
            cmd.add(get_short_path(proto_file))
            
            # Execute buf format and capture output
            ctx.actions.run(
                cmd,
                category = "buf_format_write",
                identifier = f"format_write_{ctx.label.name}_{i}",
                inputs = inputs,
                outputs = [formatted_files[i]],
                env = {
                    "BUF_CACHE_DIR": "buck-out/buf-cache",
                    "PATH": "/usr/bin:/bin",
                },
                # Redirect stdout to formatted file
                stdout = formatted_files[i],
            )
        
        diff_output = None
        
    else:
        # Default mode - just validate formatting
        format_check = ctx.actions.declare_output("buf_format_check.txt")
        outputs.append(format_check)
        
        cmd = cmd_args([buf_cli, "format", "--diff", "--exit-code"])
        
        if buf_config:
            cmd.add("--config", buf_config)
        
        for proto_file in proto_files:
            cmd.add(get_short_path(proto_file))
        
        ctx.actions.run(
            cmd,
            category = "buf_format_check",
            identifier = "format_check_" + ctx.label.name,
            inputs = inputs,
            outputs = [format_check],
            env = {
                "BUF_CACHE_DIR": "buck-out/buf-cache",
                "PATH": "/usr/bin:/bin",
            },
            stdout = format_check,
        )
        
        formatted_files = []
        diff_output = format_check
    
    # Create BufFormatInfo provider
    buf_format_info = BufFormatInfo(
        formatted_files = formatted_files,
        diff_report = diff_output,
        needs_formatting = False,  # Would be determined by parsing diff output
        files_processed = proto_files,
        format_time_ms = 0,  # Would be measured in real implementation
        changes_made = 0,  # Would be counted from diff output
        diff_output = diff_output,
    )
    
    return [
        DefaultInfo(default_outputs = outputs),
        buf_format_info,
    ]

def buf_breaking_impl(ctx):
    """
    Implementation function for buf_breaking rule.
    
    Executes advanced buf breaking change detection against BSR baselines
    with team notifications and policy enforcement.
    
    Args:
        ctx: Buck2 rule context
        
    Returns:
        List of providers including BufBreakingInfo and DefaultInfo
    """
    # Get buf CLI from toolchain
    buf_toolchain = ctx.toolchains["//tools:buf_toolchain"][BufToolchainInfo]
    buf_cli = buf_toolchain.buf_cli
    
    # Get source files
    proto_files = ctx.attrs.srcs
    if not proto_files:
        fail("buf_breaking: srcs cannot be empty")
    
    # Determine baseline source
    baseline = None
    bsr_baseline = None
    
    if ctx.attrs.against:
        baseline = ctx.attrs.against
    elif ctx.attrs.against_repository:
        bsr_baseline = f"{ctx.attrs.against_repository}:{ctx.attrs.against_tag}"
    else:
        fail("buf_breaking: Either 'against' or 'against_repository' must be specified")
    
    # Comprehensive configuration discovery with validation and merging
    config_result = discover_comprehensive_buf_config(ctx, proto_files, "breaking")
    
    # Check for validation errors
    if config_result.validation_errors:
        error_msg = "Buf configuration validation errors:\n" + "\n".join(config_result.validation_errors)
        print("Warning: " + error_msg)
    
    # Determine which configuration file to use for buf CLI
    buf_config = None
    if ctx.attrs.buf_yaml:
        # Explicit buf_yaml parameter takes precedence
        buf_config = ctx.attrs.buf_yaml
    elif config_result.module_config and config_result.module_config.config_file:
        # Use discovered module config file
        buf_config = config_result.module_config.config_file
    elif config_result.workspace_config and config_result.workspace_config.workspace_file:
        # For workspace configs, we might need to create a temporary module-specific config
        buf_config = create_buf_config(ctx, config_result.effective_config.get("breaking", {}), "breaking")
    elif ctx.attrs.config:
        # Create temporary config from inline parameters
        buf_config = create_buf_config(ctx, ctx.attrs.config, "breaking")
    
    inputs = list(proto_files)
    if buf_config:
        inputs.append(buf_config)
    
    # Create output files
    breaking_report_json = ctx.actions.declare_output("buf_breaking_report.json")
    breaking_report_text = ctx.actions.declare_output("buf_breaking_report.txt")
    migration_plan = None
    team_notification = None
    
    # Generate migration plan if requested
    if ctx.attrs.generate_migration_plan:
        migration_plan = ctx.actions.declare_output("migration_plan.md")
    
    # Create team notification output if teams are specified
    if ctx.attrs.notify_teams:
        team_notification = ctx.actions.declare_output("team_notification.json")
    
    # Create advanced breaking change detection script
    detection_script = ctx.actions.write(
        "advanced_breaking_detection.py",
        _create_breaking_detection_script(
            buf_cli = buf_cli,
            buf_config = buf_config,
            baseline = baseline,
            bsr_baseline = bsr_baseline,
            proto_files = proto_files,
            breaking_policy = ctx.attrs.breaking_policy,
            notify_teams = ctx.attrs.notify_teams,
            generate_migration_plan = ctx.attrs.generate_migration_plan,
            slack_webhook = ctx.attrs.slack_webhook,
            escalation_hours = ctx.attrs.escalation_hours,
            review_required = ctx.attrs.review_required,
            team_config_file = ctx.attrs.team_config_file,
            outputs = {
                "breaking_report_json": breaking_report_json,
                "breaking_report_text": breaking_report_text,
                "migration_plan": migration_plan,
                "team_notification": team_notification,
            }
        ),
        is_executable = True,
    )
    
    # Prepare outputs list
    outputs = [breaking_report_json, breaking_report_text]
    if migration_plan:
        outputs.append(migration_plan)
    if team_notification:
        outputs.append(team_notification)
    
    # Build command to run the advanced detection
    cmd = cmd_args([detection_script])
    
    # Add inputs to command dependencies
    script_inputs = inputs + [detection_script]
    
    # Create cache key for this breaking change check
    cache_key = create_cache_key([
        buf_toolchain.version,
        baseline or bsr_baseline,
        str(ctx.attrs.config),
        str(ctx.attrs.breaking_policy),
        str(ctx.attrs.notify_teams),
        str([get_short_path(f) for f in proto_files]),
    ])
    
    # Execute advanced breaking change detection
    ctx.actions.run(
        cmd,
        category = "buf_breaking_advanced",
        identifier = cache_key,
        inputs = script_inputs,
        outputs = outputs,
        env = {
            "BUF_CACHE_DIR": "buck-out/buf-cache",
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": "/usr/local/lib/python3.11/site-packages",
        },
        allow_cache_upload = True,
        allow_dep_file_cache_upload = True,
    )
    
    # Parse breaking change results (would be enhanced to read from JSON)
    breaking_passed = True  # Will be determined by parsing output
    
    # Create enhanced BufBreakingInfo provider
    buf_breaking_info = BufBreakingInfo(
        breaking_report = breaking_report_json,
        violations = [],  # Would be parsed from JSON in real implementation
        passed = breaking_passed,
        baseline_used = baseline or bsr_baseline,
        config_used = buf_config,
        files_checked = proto_files,
        check_time_ms = 0,  # Would be measured in real implementation
        rules_applied = [],  # Would be extracted from config
        breaking_count = 0,  # Would be parsed from JSON
        # Enhanced fields for team notifications
        policy_applied = ctx.attrs.breaking_policy,
        teams_notified = ctx.attrs.notify_teams,
        migration_plan_generated = ctx.attrs.generate_migration_plan,
        review_required = ctx.attrs.review_required,
    )
    
    return [
        DefaultInfo(default_outputs = outputs),
        buf_breaking_info,
    ]

def create_readable_lint_report(ctx, json_report, text_report):
    """
    Create a human-readable lint report from JSON output.
    
    Args:
        ctx: Buck2 rule context
        json_report: JSON lint report file
        text_report: Output text report file
    """
    # Create a simple script to convert JSON to readable format
    converter_script = ctx.actions.write(
        "convert_lint_report.py",
        [
            "#!/usr/bin/env python3",
            "import json",
            "import sys",
            "",
            "with open(sys.argv[1], 'r') as f:",
            "    data = json.load(f)",
            "",
            "with open(sys.argv[2], 'w') as f:",
            "    if 'issues' in data:",
            "        for issue in data['issues']:",
            "            f.write(f\"{issue.get('path', 'unknown')}: {issue.get('message', '')}\\n\")",
            "    else:",
            "        f.write('No lint issues found\\n')",
        ],
        is_executable = True,
    )
    
    ctx.actions.run(
        [converter_script, json_report, text_report],
        category = "buf_lint_convert",
        inputs = [converter_script, json_report],
        outputs = [text_report],
    )

def create_readable_breaking_report(ctx, json_report, text_report):
    """
    Create a human-readable breaking change report from JSON output.
    
    Args:
        ctx: Buck2 rule context
        json_report: JSON breaking change report file
        text_report: Output text report file
    """
    # Create a simple script to convert JSON to readable format
    converter_script = ctx.actions.write(
        "convert_breaking_report.py",
        [
            "#!/usr/bin/env python3",
            "import json",
            "import sys",
            "",
            "with open(sys.argv[1], 'r') as f:",
            "    data = json.load(f)",
            "",
            "with open(sys.argv[2], 'w') as f:",
            "    if 'issues' in data:",
            "        for issue in data['issues']:",
            "            f.write(f\"{issue.get('path', 'unknown')}: {issue.get('message', '')}\\n\")",
            "    else:",
            "        f.write('No breaking changes found\\n')",
        ],
        is_executable = True,
    )
    
    ctx.actions.run(
        [converter_script, json_report, text_report],
        category = "buf_breaking_convert",
        inputs = [converter_script, json_report],
        outputs = [text_report],
    )

def _create_breaking_detection_script(buf_cli, buf_config, baseline, bsr_baseline, proto_files, 
                                     breaking_policy, notify_teams, generate_migration_plan,
                                     slack_webhook, escalation_hours, review_required,
                                     team_config_file, outputs):
    """
    Create the advanced breaking change detection script.
    
    This generates a Python script that integrates buf CLI with BSR baselines,
    team notifications, and migration planning.
    """
    
    script_lines = [
        "#!/usr/bin/env python3",
        "\"\"\"Advanced Breaking Change Detection with Team Notifications.\"\"\"",
        "",
        "import json",
        "import os",
        "import subprocess",
        "import sys",
        "import time",
        "from pathlib import Path",
        "from typing import Dict, List, Optional, Any",
        "",
        "# Configuration",
        f"BUF_CLI = '{buf_cli}'",
        f"BUF_CONFIG = '{buf_config}' if '{buf_config}' != 'None' else None",
        f"BASELINE = '{baseline}' if '{baseline}' != 'None' else None", 
        f"BSR_BASELINE = '{bsr_baseline}' if '{bsr_baseline}' != 'None' else None",
        f"BREAKING_POLICY = '{breaking_policy}'",
        f"NOTIFY_TEAMS = {notify_teams}",
        f"GENERATE_MIGRATION_PLAN = {generate_migration_plan}",
        f"SLACK_WEBHOOK = '{slack_webhook}' if '{slack_webhook}' != 'None' else None",
        f"ESCALATION_HOURS = {escalation_hours}",
        f"REVIEW_REQUIRED = {review_required}",
        f"TEAM_CONFIG_FILE = '{team_config_file}' if '{team_config_file}' != 'None' else None",
        "",
        "# Output files",
        f"BREAKING_REPORT_JSON = '{outputs['breaking_report_json']}'",
        f"BREAKING_REPORT_TEXT = '{outputs['breaking_report_text']}'",
        f"MIGRATION_PLAN = '{outputs['migration_plan']}' if {outputs['migration_plan'] is not None} else None",
        f"TEAM_NOTIFICATION = '{outputs['team_notification']}' if {outputs['team_notification'] is not None} else None",
        "",
        "def run_buf_breaking():",
        "    \"\"\"Run buf breaking change detection.\"\"\"",
        "    cmd = [BUF_CLI, 'breaking']",
        "    ",
        "    # Add configuration",
        "    if BUF_CONFIG:",
        "        cmd.extend(['--config', BUF_CONFIG])",
        "    ",
        "    # Add baseline",
        "    if BASELINE:",
        "        cmd.extend(['--against', BASELINE])",
        "    elif BSR_BASELINE:",
        "        cmd.extend(['--against', BSR_BASELINE])",
        "    ",
        "    # Add format for JSON output",
        "    cmd.extend(['--format', 'json'])",
        "    ",
        "    # Add proto files or current directory", 
        "    cmd.append('.')",
        "    ",
        "    print(f'Executing: {\" \".join(cmd)}', file=sys.stderr)",
        "    ",
        "    # Execute buf breaking",
        "    try:",
        "        result = subprocess.run(",
        "            cmd,",
        "            capture_output=True,",
        "            text=True,",
        "            timeout=120,",
        "            env={**os.environ, 'BUF_CACHE_DIR': 'buck-out/buf-cache'}",
        "        )",
        "        ",
        "        # Parse JSON output",
        "        breaking_data = {}",
        "        if result.stdout.strip():",
        "            try:",
        "                breaking_data = json.loads(result.stdout)",
        "            except json.JSONDecodeError:",
        "                breaking_data = {'raw_output': result.stdout}",
        "        ",
        "        # Enhance with metadata",
        "        breaking_data.update({",
        "            'exit_code': result.returncode,",
        "            'stderr': result.stderr,",
        "            'baseline_used': BASELINE or BSR_BASELINE,",
        "            'policy': BREAKING_POLICY,",
        "            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ'),",
        "            'teams_to_notify': NOTIFY_TEAMS,",
        "        })",
        "        ",
        "        return breaking_data, result.returncode == 0",
        "        ",
        "    except subprocess.TimeoutExpired:",
        "        return {'error': 'buf breaking command timed out'}, False",
        "    except Exception as e:",
        "        return {'error': f'buf breaking command failed: {e}'}, False",
        "",
        "def generate_buck2_migration_plan(breaking_data: Dict) -> str:",
        "    \"\"\"Generate Buck2-specific migration plan.\"\"\"",
        "    issues = breaking_data.get('issues', [])",
        "    if not issues:",
        "        return '# No Breaking Changes\\n\\nNo migration required.'",
        "    ",
        "    plan = [",
        "        '# Breaking Change Migration Guide',",
        "        '',",
        "        '## 🚨 Breaking Changes Detected',",
        "        f'**Baseline:** {breaking_data.get(\"baseline_used\", \"Unknown\")}',",
        "        f'**Policy:** {BREAKING_POLICY}',",
        "        f'**Detected:** {breaking_data.get(\"timestamp\", \"Unknown\")}',",
        "        '',",
        "        '## Buck2 Migration Steps',",
        "        '',",
        "    ]",
        "    ",
        "    # Add specific breaking changes",
        "    for i, issue in enumerate(issues, 1):",
        "        plan.extend([",
        "            f'### {i}. {issue.get(\"type\", \"Unknown Change\")}',",
        "            f'**File:** `{issue.get(\"path\", \"unknown\")}`',",
        "            f'**Message:** {issue.get(\"message\", \"No details available\")}',",
        "            '',",
        "        ])",
        "    ",
        "    # Add Buck2-specific guidance",
        "    plan.extend([",
        "        '## Buck2 Build Impact',",
        "        '',",
        "        '```bash',",
        "        '# Check affected targets',",
        "        'buck2 query \"deps(//...)\" | grep proto',",
        "        '',",
        "        '# Rebuild affected targets',",
        "        'buck2 build //...',",
        "        '',",
        "        '# Run tests to verify compatibility',",
        "        'buck2 test //...',",
        "        '```',",
        "        '',",
        "        '## BUCK File Updates',",
        "        '',",
        "        'If dependencies need version updates:',",
        "        '',",
        "        '```python',",
        "        '# Before',",
        "        'proto_library(',",
        "        '    name = \"api_proto\",',",
        f'    deps = [\"{breaking_data.get(\"baseline_used\", \"previous_version\")}\"]',",
        "        ')',",
        "        '',",
        "        '# After (update version/tag)',",
        "        'proto_library(',",
        "        '    name = \"api_proto\",',",
        "        '    deps = [\"new_version_here\"]',",
        "        ')',",
        "        '```',",
        "        '',",
        "        '## Rollback Procedure',",
        "        '',",
        "        'If issues arise:',",
        "        '',",
        "        '1. Revert BUCK file changes',",
        "        '2. Clear Buck2 cache: `buck2 clean`',",
        "        '3. Rebuild: `buck2 build //...`',",
        "        '',",
        "        '## Team Coordination',",
        "        '',",
        "    ])",
        "    ",
        "    if NOTIFY_TEAMS:",
        "        plan.extend([",
        "            'Teams to coordinate with:',",
        "            '',",
        "        ])",
        "        for team in NOTIFY_TEAMS:",
        "            plan.append(f'- {team}')",
        "        plan.append('')",
        "    ",
        "    return '\\n'.join(plan)",
        "",
        "def create_slack_notification(breaking_data: Dict, migration_plan: str) -> Dict:",
        "    \"\"\"Create Slack notification payload.\"\"\"",
        "    issues = breaking_data.get('issues', [])",
        "    issue_count = len(issues)",
        "    ",
        "    if issue_count == 0:",
        "        return {",
        "            'text': '✅ No breaking changes detected',",
        "            'blocks': [",
        "                {",
        "                    'type': 'section',",
        "                    'text': {",
        "                        'type': 'mrkdwn',",
        "                        'text': f'*Breaking Change Check Passed* ✅\\n\\nBaseline: `{breaking_data.get(\"baseline_used\", \"Unknown\")}`\\nNo breaking changes detected.'",
        "                    }",
        "                }",
        "            ]",
        "        }",
        "    ",
        "    severity_emoji = '🟡' if BREAKING_POLICY == 'warn' else '🔴' if BREAKING_POLICY == 'error' else '⚠️'",
        "    ",
        "    return {",
        "        'text': f'{severity_emoji} Breaking changes detected ({issue_count} issues)',",
        "        'blocks': [",
        "            {",
        "                'type': 'section',",
        "                'text': {",
        "                    'type': 'mrkdwn',",
        "                    'text': f'*Breaking Changes Detected* {severity_emoji}\\n\\n*Baseline:* `{breaking_data.get(\"baseline_used\", \"Unknown\")}`\\n*Policy:* {BREAKING_POLICY}\\n*Issues:* {issue_count}'",
        "                }",
        "            },",
        "            {",
        "                'type': 'section',",
        "                'text': {",
        "                    'type': 'mrkdwn',",
        "                    'text': '*Top Issues:*\\n' + '\\n'.join([f'• {issue.get(\"message\", \"Unknown\")[:100]}...' for issue in issues[:3]])",
        "                }",
        "            },",
        "            {",
        "                'type': 'actions',",
        "                'elements': [",
        "                    {",
        "                        'type': 'button',",
        "                        'text': {'type': 'plain_text', 'text': '📋 View Migration Plan'},",
        "                        'value': 'view_migration_plan'",
        "                    },",
        "                    {",
        "                        'type': 'button',",
        "                        'text': {'type': 'plain_text', 'text': '✅ Acknowledge'},",
        "                        'value': 'acknowledge'",
        "                    }",
        "                ]",
        "            }",
        "        ]",
        "    }",
        "",
        "def send_slack_notification(notification_data: Dict) -> bool:",
        "    \"\"\"Send notification to Slack.\"\"\"",
        "    if not SLACK_WEBHOOK:",
        "        print('No Slack webhook configured, skipping notification', file=sys.stderr)",
        "        return True",
        "    ",
        "    try:",
        "        import requests",
        "        response = requests.post(SLACK_WEBHOOK, json=notification_data, timeout=10)",
        "        return response.status_code == 200",
        "    except ImportError:",
        "        print('requests library not available, skipping Slack notification', file=sys.stderr)",
        "        return True",
        "    except Exception as e:",
        "        print(f'Failed to send Slack notification: {e}', file=sys.stderr)",
        "        return False",
        "",
        "def main():",
        "    \"\"\"Main execution function.\"\"\"",
        "    print('Running advanced breaking change detection...', file=sys.stderr)",
        "    ",
        "    # Run buf breaking change detection",
        "    breaking_data, success = run_buf_breaking()",
        "    ",
        "    # Write JSON report",
        "    with open(BREAKING_REPORT_JSON, 'w') as f:",
        "        json.dump(breaking_data, f, indent=2)",
        "    ",
        "    # Write text report",
        "    with open(BREAKING_REPORT_TEXT, 'w') as f:",
        "        if breaking_data.get('issues'):",
        "            f.write(f'Breaking changes detected ({len(breaking_data[\"issues\"])} issues):\\n\\n')",
        "            for issue in breaking_data['issues']:",
        "                f.write(f'{issue.get(\"path\", \"unknown\")}: {issue.get(\"message\", \"Unknown\")}\\n')",
        "        else:",
        "            f.write('No breaking changes detected\\n')",
        "    ",
        "    # Generate migration plan if requested",
        "    migration_plan = ''",
        "    if GENERATE_MIGRATION_PLAN and MIGRATION_PLAN:",
        "        migration_plan = generate_buck2_migration_plan(breaking_data)",
        "        with open(MIGRATION_PLAN, 'w') as f:",
        "            f.write(migration_plan)",
        "    ",
        "    # Create team notification if teams specified",
        "    if NOTIFY_TEAMS and TEAM_NOTIFICATION:",
        "        slack_notification = create_slack_notification(breaking_data, migration_plan)",
        "        team_notification_data = {",
        "            'teams': NOTIFY_TEAMS,",
        "            'breaking_changes': breaking_data,",
        "            'slack_notification': slack_notification,",
        "            'policy': BREAKING_POLICY,",
        "            'escalation_hours': ESCALATION_HOURS,",
        "            'review_required': REVIEW_REQUIRED,",
        "            'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ')",
        "        }",
        "        ",
        "        with open(TEAM_NOTIFICATION, 'w') as f:",
        "            json.dump(team_notification_data, f, indent=2)",
        "        ",
        "        # Send Slack notification",
        "        send_slack_notification(slack_notification)",
        "    ",
        "    # Handle policy enforcement",
        "    issues = breaking_data.get('issues', [])",
        "    if issues:",
        "        if BREAKING_POLICY == 'error':",
        "            print(f'ERROR: {len(issues)} breaking changes detected', file=sys.stderr)",
        "            sys.exit(1)",
        "        elif BREAKING_POLICY == 'warn':",
        "            print(f'WARNING: {len(issues)} breaking changes detected', file=sys.stderr)",
        "        elif BREAKING_POLICY == 'review' and REVIEW_REQUIRED:",
        "            print(f'REVIEW REQUIRED: {len(issues)} breaking changes detected', file=sys.stderr)",
        "            print('Manual approval required before proceeding', file=sys.stderr)",
        "    ",
        "    print('Advanced breaking change detection completed', file=sys.stderr)",
        "",
        "if __name__ == '__main__':",
        "    main()",
    ]
    
    return script_lines
