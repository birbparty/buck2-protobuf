"""Security rules and configuration for protobuf Buck2 integration.

This module provides security configuration rules that allow users to customize
security settings for protobuf code generation while maintaining strong defaults.
"""

load("//rules/private:security_impl.bzl", 
     "create_sandbox_config", 
     "create_security_audit_info",
     "secure_protoc_execution")
load("//rules/private:providers.bzl", 
     "SecurityAuditInfo", 
     "SandboxConfigInfo", 
     "SecurityReportInfo")

def security_config(
    name,
    sandbox_enabled = True,
    network_allowed = False,
    max_memory_mb = 1024,
    max_cpu_time_seconds = 300,
    max_processes = 1,
    read_only_paths = None,
    write_paths = None,
    allowed_env_vars = None,
    input_sanitization = True,
    tool_validation = True,
    generated_code_validation = True,
    audit_logging = True,
    security_level = "strict",
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Defines security configuration for protobuf code generation.
    
    This rule allows customization of security settings while maintaining
    secure defaults. It provides comprehensive controls for sandboxing,
    validation, and auditing.
    
    Args:
        name: Unique name for this security configuration
        sandbox_enabled: Whether to enable sandboxed execution (default: True)
        network_allowed: Whether to allow network access (default: False)
        max_memory_mb: Maximum memory limit in MB (default: 1024)
        max_cpu_time_seconds: Maximum CPU time in seconds (default: 300)
        max_processes: Maximum number of processes (default: 1)
        read_only_paths: List of read-only path patterns
        write_paths: List of writable path patterns
        allowed_env_vars: List of allowed environment variables
        input_sanitization: Whether to sanitize proto inputs (default: True)
        tool_validation: Whether to validate tool integrity (default: True)
        generated_code_validation: Whether to validate generated code (default: True)
        audit_logging: Whether to enable audit logging (default: True)
        security_level: Security level: "strict", "standard", or "relaxed" (default: "strict")
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    
    Example:
        security_config(
            name = "enterprise_security",
            security_level = "strict",
            max_memory_mb = 2048,
            max_cpu_time_seconds = 600,
            audit_logging = True,
            visibility = ["PUBLIC"],
        )
        
        security_config(
            name = "development_security",
            security_level = "standard",
            max_memory_mb = 4096,
            network_allowed = False,  # Still no network in development
            audit_logging = False,
            visibility = ["//dev:__pkg__"],
        )
    """
    # Validate security level
    valid_levels = ["strict", "standard", "relaxed"]
    if security_level not in valid_levels:
        fail("security_level must be one of: {}".format(valid_levels))
    
    # Apply security level defaults
    if security_level == "strict":
        # Strictest security settings
        sandbox_enabled = True
        network_allowed = False
        input_sanitization = True
        tool_validation = True
        generated_code_validation = True
        audit_logging = True
        if max_memory_mb > 2048:
            print("WARNING: High memory limit ({} MB) in strict security mode".format(max_memory_mb))
    elif security_level == "standard":
        # Balanced security settings
        sandbox_enabled = True
        network_allowed = False
        input_sanitization = True
        tool_validation = True
        # Allow some relaxation for development
        if not generated_code_validation:
            print("INFO: Generated code validation disabled in standard mode")
    elif security_level == "relaxed":
        # More permissive for special cases
        print("WARNING: Using relaxed security mode - not recommended for production")
        if network_allowed:
            print("WARNING: Network access enabled in relaxed mode")
    
    security_config_rule(
        name = name,
        sandbox_enabled = sandbox_enabled,
        network_allowed = network_allowed,
        max_memory_mb = max_memory_mb,
        max_cpu_time_seconds = max_cpu_time_seconds,
        max_processes = max_processes,
        read_only_paths = read_only_paths or [],
        write_paths = write_paths or [],
        allowed_env_vars = allowed_env_vars or [],
        input_sanitization = input_sanitization,
        tool_validation = tool_validation,
        generated_code_validation = generated_code_validation,
        audit_logging = audit_logging,
        security_level = security_level,
        visibility = visibility,
        **kwargs
    )

def _security_config_impl(ctx):
    """Implementation function for security_config rule."""
    
    # Create sandbox configuration
    sandbox_config = create_sandbox_config(
        network_allowed = ctx.attrs.network_allowed,
        max_memory_mb = ctx.attrs.max_memory_mb,
        max_cpu_time_seconds = ctx.attrs.max_cpu_time_seconds,
        max_processes = ctx.attrs.max_processes,
        read_only_paths = ctx.attrs.read_only_paths,
        write_paths = ctx.attrs.write_paths,
        allowed_env_vars = ctx.attrs.allowed_env_vars,
    )
    
    # Create sandbox config info provider
    sandbox_info = SandboxConfigInfo(
        network_allowed = ctx.attrs.network_allowed,
        max_memory_mb = ctx.attrs.max_memory_mb,
        max_cpu_time_seconds = ctx.attrs.max_cpu_time_seconds,
        max_processes = ctx.attrs.max_processes,
        read_only_paths = ctx.attrs.read_only_paths,
        write_paths = ctx.attrs.write_paths,
        allowed_env_vars = ctx.attrs.allowed_env_vars,
    )
    
    # Create configuration file for runtime use
    config_file = ctx.actions.declare_output("security_config.json")
    config_content = {
        "sandbox_enabled": ctx.attrs.sandbox_enabled,
        "network_allowed": ctx.attrs.network_allowed,
        "max_memory_mb": ctx.attrs.max_memory_mb,
        "max_cpu_time_seconds": ctx.attrs.max_cpu_time_seconds,
        "max_processes": ctx.attrs.max_processes,
        "read_only_paths": ctx.attrs.read_only_paths,
        "write_paths": ctx.attrs.write_paths,
        "allowed_env_vars": ctx.attrs.allowed_env_vars,
        "input_sanitization": ctx.attrs.input_sanitization,
        "tool_validation": ctx.attrs.tool_validation,
        "generated_code_validation": ctx.attrs.generated_code_validation,
        "audit_logging": ctx.attrs.audit_logging,
        "security_level": ctx.attrs.security_level,
    }
    
    ctx.actions.write(
        config_file,
        json.encode(config_content)
    )
    
    return [
        DefaultInfo(default_outputs = [config_file]),
        sandbox_info,
    ]

# Security configuration rule definition
security_config_rule = rule(
    impl = _security_config_impl,
    attrs = {
        "sandbox_enabled": attrs.bool(default = True, doc = "Enable sandboxed execution"),
        "network_allowed": attrs.bool(default = False, doc = "Allow network access"),
        "max_memory_mb": attrs.int(default = 1024, doc = "Maximum memory in MB"),
        "max_cpu_time_seconds": attrs.int(default = 300, doc = "Maximum CPU time in seconds"),
        "max_processes": attrs.int(default = 1, doc = "Maximum number of processes"),
        "read_only_paths": attrs.list(attrs.string(), default = [], doc = "Read-only paths"),
        "write_paths": attrs.list(attrs.string(), default = [], doc = "Writable paths"),
        "allowed_env_vars": attrs.list(attrs.string(), default = [], doc = "Allowed environment variables"),
        "input_sanitization": attrs.bool(default = True, doc = "Enable input sanitization"),
        "tool_validation": attrs.bool(default = True, doc = "Enable tool validation"),
        "generated_code_validation": attrs.bool(default = True, doc = "Enable generated code validation"),
        "audit_logging": attrs.bool(default = True, doc = "Enable audit logging"),
        "security_level": attrs.string(default = "strict", doc = "Security level"),
    },
)

def security_audit(
    name,
    targets,
    output_format = "json",
    include_tool_validations = True,
    include_code_validations = True,
    include_audit_logs = True,
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Creates a comprehensive security audit report for protobuf targets.
    
    This rule aggregates security information from multiple targets and
    creates a comprehensive audit report for compliance and security review.
    
    Args:
        name: Unique name for this security audit
        targets: List of protobuf targets to audit
        output_format: Output format: "json", "html", or "csv" (default: "json")
        include_tool_validations: Include tool validation results (default: True)
        include_code_validations: Include code validation results (default: True)
        include_audit_logs: Include detailed audit logs (default: True)
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments
    
    Example:
        security_audit(
            name = "production_security_audit",
            targets = [
                "//services:user_proto",
                "//services:auth_proto",
                "//common:types_proto",
            ],
            output_format = "json",
            visibility = ["//security:__pkg__"],
        )
    """
    security_audit_rule(
        name = name,
        targets = targets,
        output_format = output_format,
        include_tool_validations = include_tool_validations,
        include_code_validations = include_code_validations,
        include_audit_logs = include_audit_logs,
        visibility = visibility,
        **kwargs
    )

def _security_audit_impl(ctx):
    """Implementation function for security_audit rule."""
    
    # Collect security information from all targets
    all_audit_logs = []
    all_security_reports = []
    all_tool_validations = []
    
    for target in ctx.attrs.targets:
        if SecurityAuditInfo in target:
            audit_info = target[SecurityAuditInfo]
            all_audit_logs.extend(audit_info.audit_logs)
            all_security_reports.extend(audit_info.security_reports)
            all_tool_validations.extend(audit_info.tool_validations)
    
    # Create comprehensive audit report
    audit_report = ctx.actions.declare_output("security_audit_report.{}".format(ctx.attrs.output_format))
    
    # Generate report content based on format
    if ctx.attrs.output_format == "json":
        report_content = {
            "audit_version": "1.0.0",
            "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
            "targets_audited": [str(target.label) for target in ctx.attrs.targets],
            "summary": {
                "total_targets": len(ctx.attrs.targets),
                "audit_logs_count": len(all_audit_logs),
                "security_reports_count": len(all_security_reports),
                "tool_validations_count": len(all_tool_validations),
            },
            "audit_logs": all_audit_logs if ctx.attrs.include_audit_logs else [],
            "security_reports": all_security_reports if ctx.attrs.include_code_validations else [],
            "tool_validations": all_tool_validations if ctx.attrs.include_tool_validations else [],
        }
        
        ctx.actions.write(
            audit_report,
            json.encode(report_content)
        )
    else:
        # For other formats, create a simple text report
        lines = [
            "Security Audit Report",
            "=====================",
            f"Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)",
            f"Targets Audited: {len(ctx.attrs.targets)}",
            f"Audit Logs: {len(all_audit_logs)}",
            f"Security Reports: {len(all_security_reports)}",
            f"Tool Validations: {len(all_tool_validations)}",
            "",
            "Targets:",
        ]
        
        for target in ctx.attrs.targets:
            lines.append(f"  - {target.label}")
        
        ctx.actions.write(
            audit_report,
            "\n".join(lines)
        )
    
    return [
        DefaultInfo(default_outputs = [audit_report]),
    ]

# Security audit rule definition
security_audit_rule = rule(
    impl = _security_audit_impl,
    attrs = {
        "targets": attrs.list(attrs.dep(), doc = "Targets to audit"),
        "output_format": attrs.string(default = "json", doc = "Output format"),
        "include_tool_validations": attrs.bool(default = True, doc = "Include tool validations"),
        "include_code_validations": attrs.bool(default = True, doc = "Include code validations"),
        "include_audit_logs": attrs.bool(default = True, doc = "Include audit logs"),
    },
)
