"""Core buf rules for Buck2.

This module provides Buck2 rules for buf operations including lint, format,
and breaking change detection. These rules integrate buf CLI operations
directly into the Buck2 build system with proper caching and error handling.
"""

load("//rules/private:buf_impl.bzl", "buf_lint_impl", "buf_format_impl", "buf_breaking_impl")
load("//rules/private:providers.bzl", "BufLintInfo", "BufFormatInfo", "BufBreakingInfo")

# Re-export providers for external use
BufLintInfo = BufLintInfo
BufFormatInfo = BufFormatInfo
BufBreakingInfo = BufBreakingInfo

def buf_lint(
    name,
    srcs,
    buf_yaml = None,
    config = {},
    fail_on_error = True,
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Run buf lint on protobuf files.
    
    This rule validates protobuf files using buf's comprehensive linting rules.
    It integrates with Buck2's caching system to prevent redundant validation
    and provides clear, actionable error messages.
    
    Args:
        name: Unique name for this lint target
        srcs: List of .proto files to lint
        buf_yaml: Optional buf.yaml configuration file path
        config: Dictionary of inline lint configuration options
        fail_on_error: Whether to fail the build on lint violations (default: True)
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments passed to underlying rule
    
    Provides:
        BufLintInfo: Information about lint results and violations
    
    Example:
        buf_lint(
            name = "lint_api",
            srcs = ["api.proto", "types.proto"],
            buf_yaml = "buf.yaml",
            config = {
                "use": ["DEFAULT", "COMMENTS"],
                "except": ["PACKAGE_VERSION_SUFFIX"],
            },
            visibility = ["PUBLIC"],
        )
    """
    buf_lint_rule(
        name = name,
        srcs = srcs,
        buf_yaml = buf_yaml,
        config = config,
        fail_on_error = fail_on_error,
        visibility = visibility,
        **kwargs
    )

def buf_format(
    name,
    srcs,
    diff = False,
    write = False,
    buf_yaml = None,
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Format protobuf files using buf format.
    
    This rule formats protobuf files according to buf's style guide.
    It can either show differences (for CI validation) or generate
    properly formatted versions of the files.
    
    Args:
        name: Unique name for this format target
        srcs: List of .proto files to format
        diff: Show formatting differences instead of formatting (default: False)
        write: Generate formatted files as outputs (default: False)
        buf_yaml: Optional buf.yaml configuration file path
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments passed to underlying rule
    
    Provides:
        BufFormatInfo: Information about formatting results and differences
    
    Example:
        buf_format(
            name = "format_api",
            srcs = ["api.proto"],
            diff = True,  # For CI validation
            visibility = ["PUBLIC"],
        )
        
        buf_format(
            name = "format_api_files",
            srcs = ["api.proto"],
            write = True,  # Generate formatted files
        )
    """
    buf_format_rule(
        name = name,
        srcs = srcs,
        diff = diff,
        write = write,
        buf_yaml = buf_yaml,
        visibility = visibility,
        **kwargs
    )

def buf_breaking(
    name,
    srcs,
    against = None,
    against_repository = None,
    against_tag = "latest",
    config = {},
    buf_yaml = None,
    breaking_policy = "warn",
    notify_teams = [],
    generate_migration_plan = False,
    slack_webhook = None,
    escalation_hours = [2, 24],
    review_required = False,
    team_config_file = None,
    visibility = ["//visibility:private"],
    **kwargs
):
    """
    Advanced breaking change detection with BSR baselines and team notifications.
    
    This rule detects breaking changes in protobuf files by comparing against
    baselines from BSR repositories or local references. It provides comprehensive
    team notification and policy enforcement capabilities.
    
    Args:
        name: Unique name for this breaking change target
        srcs: List of .proto files to check for breaking changes
        against: Local baseline to compare against (file path, git ref, or Buck2 target)
        against_repository: BSR repository baseline (e.g., "buf.build/myorg/api")
        against_tag: BSR tag/version to compare against (default: "latest")
        config: Dictionary of breaking change detection configuration
        buf_yaml: Optional buf.yaml configuration file path
        breaking_policy: Policy for handling breaking changes ("warn", "error", "review")
        notify_teams: List of teams to notify on breaking changes
        generate_migration_plan: Generate Buck2-specific migration guidance
        slack_webhook: Slack webhook URL for notifications
        escalation_hours: Hours after which to escalate notifications [2, 24]
        review_required: Require manual approval for breaking changes
        team_config_file: Path to team configuration file
        visibility: Buck2 visibility specification
        **kwargs: Additional arguments passed to underlying rule
    
    Provides:
        BufBreakingInfo: Information about breaking changes detected
    
    Examples:
        # Basic BSR baseline check
        buf_breaking(
            name = "check_api_breaking",
            srcs = [":api_proto"],
            against_repository = "buf.build/myorg/api",
            against_tag = "v1.2.0",
            breaking_policy = "warn",
        )
        
        # Team notifications with migration planning
        buf_breaking(
            name = "platform_breaking_check",
            srcs = ["//platform:all_protos"],
            against_repository = "oras.birb.homes/platform/core",
            breaking_policy = "review",
            notify_teams = ["@platform-team", "@api-consumers"],
            generate_migration_plan = True,
            slack_webhook = "https://hooks.slack.com/services/...",
            escalation_hours = [1, 6, 24],
            review_required = True,
        )
        
        # Local baseline (backward compatibility)
        buf_breaking(
            name = "check_against_main",
            srcs = ["**/*.proto"],
            against = "git#branch=main",
            breaking_policy = "error",
        )
    """
    # Validate arguments
    if not against and not against_repository:
        fail("buf_breaking: Either 'against' or 'against_repository' must be specified")
    
    if against and against_repository:
        fail("buf_breaking: Cannot specify both 'against' and 'against_repository'")
    
    valid_policies = ["warn", "error", "review"]
    if breaking_policy not in valid_policies:
        fail(f"buf_breaking: breaking_policy must be one of {valid_policies}")
    
    buf_breaking_rule(
        name = name,
        srcs = srcs,
        against = against,
        against_repository = against_repository,
        against_tag = against_tag,
        config = config,
        buf_yaml = buf_yaml,
        breaking_policy = breaking_policy,
        notify_teams = notify_teams,
        generate_migration_plan = generate_migration_plan,
        slack_webhook = slack_webhook,
        escalation_hours = escalation_hours,
        review_required = review_required,
        team_config_file = team_config_file,
        visibility = visibility,
        **kwargs
    )

# Rule definitions with proper attributes
buf_lint_rule = rule(
    impl = buf_lint_impl,
    attrs = {
        "srcs": attrs.list(attrs.source(), doc = "Proto source files to lint"),
        "buf_yaml": attrs.option(attrs.source(), doc = "buf.yaml configuration file"),
        "config": attrs.dict(
            attrs.string(), 
            attrs.string(), 
            default = {}, 
            doc = "Inline lint configuration options"
        ),
        "fail_on_error": attrs.bool(
            default = True, 
            doc = "Whether to fail build on lint violations"
        ),
        "_buf_toolchain": attrs.toolchain_dep(
            default = "//tools:buf_toolchain",
            providers = ["BufToolchainInfo"],
        ),
    },
    toolchains = ["//tools:buf_toolchain"],
)

buf_format_rule = rule(
    impl = buf_format_impl,
    attrs = {
        "srcs": attrs.list(attrs.source(), doc = "Proto source files to format"),
        "diff": attrs.bool(default = False, doc = "Show formatting differences"),
        "write": attrs.bool(default = False, doc = "Generate formatted files"),
        "buf_yaml": attrs.option(attrs.source(), doc = "buf.yaml configuration file"),
        "_buf_toolchain": attrs.toolchain_dep(
            default = "//tools:buf_toolchain",
            providers = ["BufToolchainInfo"],
        ),
    },
    toolchains = ["//tools:buf_toolchain"],
)

buf_breaking_rule = rule(
    impl = buf_breaking_impl,
    attrs = {
        "srcs": attrs.list(attrs.source(), doc = "Proto source files to check"),
        "against": attrs.option(attrs.string(), doc = "Local baseline to compare against"),
        "against_repository": attrs.option(attrs.string(), doc = "BSR repository baseline"),
        "against_tag": attrs.string(default = "latest", doc = "BSR tag/version to compare against"),
        "config": attrs.dict(
            attrs.string(), 
            attrs.string(), 
            default = {}, 
            doc = "Breaking change detection configuration"
        ),
        "buf_yaml": attrs.option(attrs.source(), doc = "buf.yaml configuration file"),
        "breaking_policy": attrs.string(default = "warn", doc = "Policy for handling breaking changes"),
        "notify_teams": attrs.list(attrs.string(), default = [], doc = "Teams to notify on breaking changes"),
        "generate_migration_plan": attrs.bool(default = False, doc = "Generate Buck2 migration guidance"),
        "slack_webhook": attrs.option(attrs.string(), doc = "Slack webhook URL for notifications"),
        "escalation_hours": attrs.list(attrs.int(), default = [2, 24], doc = "Hours for escalation timeline"),
        "review_required": attrs.bool(default = False, doc = "Require manual approval for breaking changes"),
        "team_config_file": attrs.option(attrs.source(), doc = "Path to team configuration file"),
        "_buf_toolchain": attrs.toolchain_dep(
            default = "//tools:buf_toolchain",
            providers = ["BufToolchainInfo"],
        ),
        "_bsr_client": attrs.toolchain_dep(
            default = "//tools:bsr_toolchain",
            providers = ["BSRToolchainInfo"],
        ),
    },
    toolchains = ["//tools:buf_toolchain", "//tools:bsr_toolchain"],
)
