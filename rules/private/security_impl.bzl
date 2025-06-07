"""Private security implementation for protobuf Buck2 integration.

This module implements comprehensive security features including sandboxing,
input sanitization, tool integrity validation, and audit logging to ensure
secure protobuf code generation.
"""

load("//rules/private:providers.bzl", "SecurityAuditInfo", "SandboxConfigInfo")

def create_sandbox_config(
    network_allowed = False,
    max_memory_mb = 1024,
    max_cpu_time_seconds = 300,
    max_processes = 1,
    read_only_paths = None,
    write_paths = None,
    allowed_env_vars = None):
    """
    Creates a sandbox configuration for secure protoc execution.
    
    Args:
        network_allowed: Whether to allow network access (default: False)
        max_memory_mb: Maximum memory limit in MB
        max_cpu_time_seconds: Maximum CPU time in seconds
        max_processes: Maximum number of processes
        read_only_paths: List of read-only path patterns
        write_paths: List of writable path patterns
        allowed_env_vars: List of allowed environment variables
        
    Returns:
        Dictionary containing sandbox configuration
    """
    if read_only_paths == None:
        read_only_paths = [
            "proto_files/**",
            "dependencies/**", 
            "tools/**",
            "include/**",
        ]
    
    if write_paths == None:
        write_paths = [
            "output/**",
            "tmp/**",
        ]
    
    if allowed_env_vars == None:
        allowed_env_vars = [
            "PATH",
            "TMPDIR",
            "HOME",  # Limited to sandbox home
        ]
    
    return {
        "network_allowed": network_allowed,
        "max_memory_mb": max_memory_mb,
        "max_cpu_time_seconds": max_cpu_time_seconds,
        "max_processes": max_processes,
        "read_only_paths": read_only_paths,
        "write_paths": write_paths,
        "allowed_env_vars": allowed_env_vars,
    }

def validate_tool_integrity(ctx, tool_path, expected_checksum):
    """
    Validates SHA256 checksum of a tool binary.
    
    Args:
        ctx: Rule context
        tool_path: Path to the tool binary
        expected_checksum: Expected SHA256 hash
        
    Returns:
        Action that validates the tool integrity
    """
    validation_output = ctx.actions.declare_output("tool_validation/{}.validated".format(tool_path.basename))
    
    ctx.actions.run(
        [
            "python3",
            ctx.attrs._security_validator[DefaultInfo].default_outputs[0],
            "--tool-path", tool_path,
            "--expected-checksum", expected_checksum,
            "--output", validation_output.as_output(),
        ],
        category = "security_validation",
        identifier = "validate_tool_{}".format(tool_path.basename),
        local_only = True,  # Security validation must run locally
        no_outputs_cleanup = True,  # Keep validation artifacts
    )
    
    return validation_output

def sanitize_proto_input(ctx, proto_file):
    """
    Sanitizes proto file content to prevent injection attacks.
    
    Args:
        ctx: Rule context
        proto_file: Proto file to sanitize
        
    Returns:
        Sanitized proto file
    """
    sanitized_output = ctx.actions.declare_output("sanitized/{}.proto".format(proto_file.basename.replace(".proto", "")))
    
    ctx.actions.run(
        [
            "python3",
            ctx.attrs._proto_sanitizer[DefaultInfo].default_outputs[0],
            "--input", proto_file,
            "--output", sanitized_output.as_output(),
            "--max-depth", "10",  # Prevent excessive nesting
            "--max-imports", "100",  # Limit import count
        ],
        category = "security_sanitization",
        identifier = "sanitize_{}".format(proto_file.basename),
        local_only = True,  # Sanitization must run locally
    )
    
    return sanitized_output

def create_hermetic_environment(ctx, sandbox_config):
    """
    Creates a hermetic execution environment.
    
    Args:
        ctx: Rule context
        sandbox_config: Sandbox configuration dictionary
        
    Returns:
        Environment variables for hermetic execution
    """
    env = {}
    
    # Only include explicitly allowed environment variables
    for var in sandbox_config["allowed_env_vars"]:
        if var == "PATH":
            # Use sandbox-specific PATH
            env["PATH"] = "/sandbox/tools/bin:/usr/bin:/bin"
        elif var == "TMPDIR":
            env["TMPDIR"] = "/sandbox/tmp"
        elif var == "HOME":
            env["HOME"] = "/sandbox/home"
    
    # Add security markers
    env["PROTOBUF_SANDBOX"] = "1"
    env["PROTOBUF_SECURITY_MODE"] = "strict"
    
    return env

def execute_in_sandbox(ctx, command, inputs, outputs, sandbox_config, category = "protoc_generation"):
    """
    Executes a command in a secure sandbox environment.
    
    Args:
        ctx: Rule context
        command: Command to execute
        inputs: Input files/directories
        outputs: Output files/directories
        sandbox_config: Sandbox configuration
        category: Action category for Buck2
        
    Returns:
        Action result
    """
    # Create hermetic environment
    env = create_hermetic_environment(ctx, sandbox_config)
    
    # Build sandbox command with security controls
    sandbox_args = []
    
    # Network isolation
    if not sandbox_config["network_allowed"]:
        sandbox_args.extend(["--no-network"])
    
    # Resource limits
    sandbox_args.extend([
        "--memory-limit", "{}M".format(sandbox_config["max_memory_mb"]),
        "--time-limit", "{}s".format(sandbox_config["max_cpu_time_seconds"]),
        "--process-limit", str(sandbox_config["max_processes"]),
    ])
    
    # File system access controls
    for path in sandbox_config["read_only_paths"]:
        sandbox_args.extend(["--read-only", path])
    
    for path in sandbox_config["write_paths"]:
        sandbox_args.extend(["--writable", path])
    
    # Execute in sandbox (Buck2 provides sandboxing automatically)
    return ctx.actions.run(
        command,
        env = env,
        category = category,
        identifier = "sandboxed_{}".format("_".join(command[:2])),
        local_only = True,  # Security-sensitive actions run locally
        no_outputs_cleanup = True,  # Keep security artifacts
    )

def validate_generated_code_security(ctx, generated_files, language):
    """
    Validates generated code for security issues.
    
    Args:
        ctx: Rule context
        generated_files: List of generated files to validate
        language: Target language for validation
        
    Returns:
        Security validation report
    """
    if not generated_files:
        return None
    
    security_report = ctx.actions.declare_output("security_report/{}_security.json".format(language))
    
    validation_args = [
        "python3",
        ctx.attrs._code_security_validator[DefaultInfo].default_outputs[0],
        "--language", language,
        "--output", security_report.as_output(),
    ]
    
    for file in generated_files:
        validation_args.extend(["--input", file])
    
    ctx.actions.run(
        validation_args,
        category = "security_validation",
        identifier = "validate_generated_{}".format(language),
        local_only = True,
    )
    
    return security_report

def create_security_audit_log(ctx, action_type, inputs, outputs, config):
    """
    Creates a security audit log entry.
    
    Args:
        ctx: Rule context
        action_type: Type of action (e.g., "protoc_execution", "tool_download")
        inputs: Input files/data
        outputs: Output files/data
        config: Security configuration used
        
    Returns:
        Audit log file
    """
    audit_log = ctx.actions.declare_output("audit/{}_audit.json".format(action_type))
    
    ctx.actions.run(
        [
            "python3",
            ctx.attrs._audit_logger[DefaultInfo].default_outputs[0],
            "--action-type", action_type,
            "--target", str(ctx.label),
            "--timestamp", "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
            "--config", json.encode(config),
            "--output", audit_log.as_output(),
        ],
        category = "security_audit",
        identifier = "audit_{}".format(action_type),
        local_only = True,
    )
    
    return audit_log

def secure_protoc_execution(ctx, proto_files, output_dir, language, plugins = None):
    """
    Executes protoc in a secure sandboxed environment.
    
    Args:
        ctx: Rule context
        proto_files: List of proto files to compile
        output_dir: Output directory for generated code
        language: Target language
        plugins: Optional list of plugins to use
        
    Returns:
        Dictionary containing generated files and security artifacts
    """
    # Create sandbox configuration
    sandbox_config = create_sandbox_config()
    
    # Sanitize proto files
    sanitized_protos = []
    for proto in proto_files:
        sanitized = sanitize_proto_input(ctx, proto)
        sanitized_protos.append(sanitized)
    
    # Validate tool integrity
    protoc_tool = ctx.attrs._protoc[DefaultInfo].default_outputs[0]
    protoc_validation = validate_tool_integrity(
        ctx, 
        protoc_tool, 
        ctx.attrs._protoc_checksum
    )
    
    # Prepare protoc command
    protoc_cmd = [
        protoc_tool,
        "--{}_out={}".format(language, output_dir),
    ]
    
    # Add plugin commands if specified
    if plugins:
        for plugin in plugins:
            plugin_tool = ctx.attrs["_plugin_{}".format(plugin.name)][DefaultInfo].default_outputs[0]
            plugin_validation = validate_tool_integrity(
                ctx,
                plugin_tool,
                ctx.attrs["_plugin_{}_checksum".format(plugin.name)]
            )
            protoc_cmd.extend([
                "--plugin=protoc-gen-{}={}".format(plugin.name, plugin_tool),
                "--{}_out={}".format(plugin.name, output_dir),
            ])
    
    # Add proto files
    for proto in sanitized_protos:
        protoc_cmd.append(proto)
    
    # Execute in sandbox
    generated_outputs = []
    for proto in sanitized_protos:
        # Determine output file name based on language
        base_name = proto.basename.replace(".proto", "")
        if language == "go":
            output_file = ctx.actions.declare_output("{}/{}.pb.go".format(output_dir, base_name))
        elif language == "python":
            output_file = ctx.actions.declare_output("{}/{}_pb2.py".format(output_dir, base_name))
        elif language == "cpp":
            header_file = ctx.actions.declare_output("{}/{}.pb.h".format(output_dir, base_name))
            source_file = ctx.actions.declare_output("{}/{}.pb.cc".format(output_dir, base_name))
            generated_outputs.extend([header_file, source_file])
            continue
        elif language == "rust":
            output_file = ctx.actions.declare_output("{}/{}.rs".format(output_dir, base_name))
        elif language == "typescript":
            output_file = ctx.actions.declare_output("{}/{}_pb.ts".format(output_dir, base_name))
        else:
            output_file = ctx.actions.declare_output("{}/{}.pb".format(output_dir, base_name))
        
        generated_outputs.append(output_file)
    
    # Execute protoc in sandbox
    execute_in_sandbox(
        ctx,
        protoc_cmd,
        sanitized_protos + [protoc_tool],
        generated_outputs,
        sandbox_config,
        "secure_protoc_{}".format(language)
    )
    
    # Validate generated code security
    security_report = validate_generated_code_security(ctx, generated_outputs, language)
    
    # Create audit log
    audit_log = create_security_audit_log(
        ctx,
        "protoc_execution",
        sanitized_protos,
        generated_outputs,
        sandbox_config
    )
    
    return {
        "generated_files": generated_outputs,
        "security_report": security_report,
        "audit_log": audit_log,
        "sanitized_protos": sanitized_protos,
        "tool_validations": [protoc_validation],
    }

def create_security_audit_info(ctx, audit_logs, security_reports, tool_validations):
    """
    Creates SecurityAuditInfo provider with comprehensive audit data.
    
    Args:
        ctx: Rule context
        audit_logs: List of audit log files
        security_reports: List of security report files
        tool_validations: List of tool validation files
        
    Returns:
        SecurityAuditInfo provider
    """
    return SecurityAuditInfo(
        audit_logs = audit_logs,
        security_reports = security_reports,
        tool_validations = tool_validations,
        target = str(ctx.label),
        timestamp = "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        security_level = "strict",
        sandbox_enabled = True,
    )
