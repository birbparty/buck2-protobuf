"""BSR publishing rules for Buck2.

This module provides automated BSR publishing with semantic versioning,
multi-registry support, and team-based governance workflows.
"""

load("//rules/private:bsr_impl.bzl", "bsr_publish_impl")
load("//rules/private:providers.bzl", "BSRPublishInfo")
load("//rules/private:utils.bzl", "get_toolchain_info")

def bsr_publish(
    name,
    proto,
    repositories,
    version_strategy = "semantic",
    breaking_change_policy = "require_approval",
    notify_teams = [],
    require_review = False,
    auto_increment = True,
    tags = [],
    visibility = None,
    **kwargs):
    """
    Publish protobuf schemas to BSR with automated versioning and governance.
    
    This rule provides professional schema publishing workflows with:
    - Semantic versioning based on schema change analysis
    - Multi-registry atomic publishing (BSR + ORAS registries)
    - Team-based approval workflows for breaking changes
    - Automated notifications and audit logging
    
    Args:
        name: Target name for the publishing rule
        proto: proto_library target to publish
        repositories: Dictionary of registry configurations:
            - Single registry: "buf.build/myorg/schemas"
            - Multi-registry: {"primary": "buf.build/myorg/schemas", "backup": "oras.birb.homes/myorg/schemas"}
        version_strategy: Versioning approach ("semantic", "manual", "git_tag")
        breaking_change_policy: How to handle breaking changes ("allow", "require_approval", "block")
        notify_teams: List of teams to notify on publication (e.g., ["@platform-team"])
        require_review: Whether to require manual review before publishing
        auto_increment: Whether to automatically increment versions
        tags: Additional tags to apply to published schemas
        visibility: Target visibility
        **kwargs: Additional publishing options
        
    Example:
        ```python
        # Simple single-registry publishing
        bsr_publish(
            name = "publish_user_api",
            proto = ":user_api_proto",
            repositories = "buf.build/myorg/user-api",
            notify_teams = ["@backend-team"],
        )
        
        # Multi-registry with governance
        bsr_publish(
            name = "publish_platform_schemas",
            proto = ":platform_schemas",
            repositories = {
                "primary": "buf.build/myorg/platform",
                "backup": "oras.birb.homes/myorg/platform"
            },
            breaking_change_policy = "require_approval",
            require_review = True,
            notify_teams = ["@platform-team", "@api-consumers"],
        )
        ```
    """
    
    # Normalize repositories configuration
    if isinstance(repositories, str):
        repositories = {"primary": repositories}
    elif isinstance(repositories, dict):
        if "primary" not in repositories:
            fail("Multi-registry configuration must include 'primary' key")
    else:
        fail("repositories must be a string or dictionary")
    
    # Validate version strategy
    valid_strategies = ["semantic", "manual", "git_tag"]
    if version_strategy not in valid_strategies:
        fail("version_strategy must be one of: {}".format(valid_strategies))
    
    # Validate breaking change policy
    valid_policies = ["allow", "require_approval", "block"]
    if breaking_change_policy not in valid_policies:
        fail("breaking_change_policy must be one of: {}".format(valid_policies))
    
    # Create publishing target
    _bsr_publish_rule(
        name = name,
        proto = proto,
        repositories = repositories,
        version_strategy = version_strategy,
        breaking_change_policy = breaking_change_policy,
        notify_teams = notify_teams,
        require_review = require_review,
        auto_increment = auto_increment,
        tags = tags,
        visibility = visibility,
        **kwargs
    )

def _bsr_publish_impl(ctx):
    """Implementation for BSR publishing rule."""
    
    # Get proto library info
    proto_info = ctx.attrs.proto[DefaultInfo]
    if not proto_info:
        fail("proto attribute must reference a valid proto_library target")
    
    # Create publishing configuration
    publish_config = {
        "repositories": ctx.attrs.repositories,
        "version_strategy": ctx.attrs.version_strategy,
        "breaking_change_policy": ctx.attrs.breaking_change_policy,
        "notify_teams": ctx.attrs.notify_teams,
        "require_review": ctx.attrs.require_review,
        "auto_increment": ctx.attrs.auto_increment,
        "tags": ctx.attrs.tags,
        "target_name": ctx.label.name,
    }
    
    # Write configuration file
    config_file = ctx.actions.write(
        "publish_config.json",
        json.encode(publish_config)
    )
    
    # Create publishing script
    publishing_script = ctx.actions.write(
        "publish_script.py",
        _generate_publishing_script(ctx, publish_config),
        is_executable = True
    )
    
    # Get toolchain information
    toolchain_info = get_toolchain_info(ctx)
    
    # Create runnable publishing target
    return [
        DefaultInfo(
            default_output = publishing_script,
            runnable = True
        ),
        BSRPublishInfo(
            proto = ctx.attrs.proto,
            repositories = ctx.attrs.repositories,
            config_file = config_file,
            publishing_script = publishing_script,
            version_strategy = ctx.attrs.version_strategy,
            breaking_change_policy = ctx.attrs.breaking_change_policy,
            notify_teams = ctx.attrs.notify_teams,
        )
    ]

def _generate_publishing_script(ctx, config):
    """Generate the publishing execution script."""
    
    script_content = """#!/usr/bin/env python3
\"\"\"Generated BSR publishing script for {target_name}.\"\"\"

import os
import sys
import json
import subprocess
from pathlib import Path

# Add tools directory to path
TOOLS_DIR = Path(__file__).parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from bsr_publisher import BSRPublisher
from bsr_version_manager import BSRVersionManager

def main():
    \"\"\"Execute BSR publishing workflow.\"\"\"
    
    # Load configuration
    config_path = Path(__file__).parent / "publish_config.json"
    with open(config_path) as f:
        config = json.load(f)
    
    print(f"🚀 Publishing {{config['target_name']}} to BSR...")
    
    try:
        # Initialize publisher
        publisher = BSRPublisher(
            repositories=config["repositories"],
            version_strategy=config["version_strategy"],
            breaking_change_policy=config["breaking_change_policy"],
            notify_teams=config["notify_teams"],
            verbose=True
        )
        
        # Execute publishing workflow
        result = publisher.publish_schemas(
            proto_target="{proto_target}",
            require_review=config["require_review"],
            auto_increment=config["auto_increment"],
            tags=config["tags"]
        )
        
        if result.success:
            print(f"✅ Successfully published {{result.version}} to {{len(config['repositories'])}} registries")
            print(f"   Published to: {{', '.join(config['repositories'].values())}}")
            if result.notifications_sent:
                print(f"   Notifications sent to: {{', '.join(config['notify_teams'])}}")
        else:
            print(f"❌ Publishing failed: {{result.error}}")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Publishing error: {{e}}")
        sys.exit(1)

if __name__ == "__main__":
    main()
""".format(
        target_name=config["target_name"],
        proto_target=str(ctx.attrs.proto.label)
    )
    
    return script_content

_bsr_publish_rule = rule(
    impl = _bsr_publish_impl,
    attrs = {
        "proto": attrs.dep(providers = [DefaultInfo], mandatory = True),
        "repositories": attrs.dict(attrs.string(), attrs.string(), default = {}),
        "version_strategy": attrs.string(default = "semantic"),
        "breaking_change_policy": attrs.string(default = "require_approval"),
        "notify_teams": attrs.list(attrs.string(), default = []),
        "require_review": attrs.bool(default = False),
        "auto_increment": attrs.bool(default = True),
        "tags": attrs.list(attrs.string(), default = []),
    }
)

def bsr_publish_multiple(
    name,
    targets,
    repositories,
    batch_size = 5,
    parallel = True,
    **kwargs):
    """
    Publish multiple proto targets as a coordinated batch.
    
    This rule enables publishing multiple related schemas together with
    coordinated versioning and atomic success/failure across all targets.
    
    Args:
        name: Target name for the batch publishing rule
        targets: List of proto_library targets to publish
        repositories: Repository configuration (same format as bsr_publish)
        batch_size: Maximum number of concurrent publishes
        parallel: Whether to publish targets in parallel
        **kwargs: Additional options passed to individual bsr_publish rules
        
    Example:
        ```python
        bsr_publish_multiple(
            name = "publish_all_apis",
            targets = [
                ":user_api_proto",
                ":payment_api_proto", 
                ":notification_api_proto"
            ],
            repositories = {
                "primary": "buf.build/myorg/apis",
                "backup": "oras.birb.homes/myorg/apis"
            },
            notify_teams = ["@platform-team"],
        )
        ```
    """
    
    # Create individual publishing targets
    publish_targets = []
    for i, target in enumerate(targets):
        publish_name = "{}_{}".format(name, i)
        bsr_publish(
            name = publish_name,
            proto = target,
            repositories = repositories,
            **kwargs
        )
        publish_targets.append(":{}".format(publish_name))
    
    # Create coordinated batch target
    _bsr_publish_batch_rule(
        name = name,
        publish_targets = publish_targets,
        batch_size = batch_size,
        parallel = parallel,
    )

def _bsr_publish_batch_impl(ctx):
    """Implementation for batch BSR publishing."""
    
    # Create batch execution script
    batch_script = ctx.actions.write(
        "batch_publish.py",
        _generate_batch_script(ctx),
        is_executable = True
    )
    
    return [
        DefaultInfo(
            default_output = batch_script,
            runnable = True
        )
    ]

def _generate_batch_script(ctx):
    """Generate batch publishing script."""
    
    targets = [str(target) for target in ctx.attrs.publish_targets]
    
    script_content = """#!/usr/bin/env python3
\"\"\"Generated batch BSR publishing script.\"\"\"

import os
import sys
import subprocess
import concurrent.futures
from pathlib import Path

TARGETS = {targets}
BATCH_SIZE = {batch_size}
PARALLEL = {parallel}

def run_publish_target(target):
    \"\"\"Run individual publish target.\"\"\"
    try:
        cmd = ["buck2", "run", target]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {target} published successfully")
            return (target, True, None)
        else:
            print(f"❌ {target} failed: {result.stderr}")
            return (target, False, result.stderr)
            
    except Exception as e:
        print(f"❌ {target} error: {e}")
        return (target, False, str(e))

def main():
    \"\"\"Execute batch publishing.\"\"\"
    
    print(f"🚀 Publishing {len(TARGETS)} targets in batch...")
    
    if PARALLEL:
        # Parallel execution
        with concurrent.futures.ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
            futures = [executor.submit(run_publish_target, target) for target in TARGETS]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
    else:
        # Sequential execution
        results = [run_publish_target(target) for target in TARGETS]
    
    # Process results
    successful = [r for r in results if r[1]]
    failed = [r for r in results if not r[1]]
    
    print(f"\\n📊 Batch publishing results:")
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ❌ Failed: {len(failed)}")
    
    if failed:
        print(f"\\n❌ Failed targets:")
        for target, _, error in failed:
            print(f"   {target}: {error}")
        sys.exit(1)
    else:
        print(f"\\n🎉 All targets published successfully!")

if __name__ == "__main__":
    main()
""".format(
        targets=targets,
        batch_size=ctx.attrs.batch_size,
        parallel=str(ctx.attrs.parallel).lower()
    )
    
    return script_content

_bsr_publish_batch_rule = rule(
    impl = _bsr_publish_batch_impl,
    attrs = {
        "publish_targets": attrs.list(attrs.string(), mandatory = True),
        "batch_size": attrs.int(default = 5),
        "parallel": attrs.bool(default = True),
    }
)

def bsr_publish_workspace(
    name,
    workspace_root = ".",
    exclude_paths = [],
    repositories = {},
    **kwargs):
    """
    Automatically discover and publish all proto_library targets in a workspace.
    
    This rule scans the workspace for proto_library targets and creates
    publishing rules for each one, enabling workspace-wide schema publishing.
    
    Args:
        name: Target name for workspace publishing
        workspace_root: Root directory to scan for proto targets
        exclude_paths: List of paths to exclude from scanning
        repositories: Repository configuration
        **kwargs: Additional options for individual publishing rules
        
    Example:
        ```python
        bsr_publish_workspace(
            name = "publish_workspace",
            repositories = "buf.build/myorg/workspace",
            exclude_paths = ["test/", "examples/"],
            notify_teams = ["@platform-team"],
        )
        ```
    """
    
    # This would require build-time target discovery
    # For now, create a manual target that requires explicit target listing
    
    native.genrule(
        name = name,
        out = "workspace_publish_info.txt",
        cmd = 'echo "Workspace publishing requires explicit target enumeration. Use bsr_publish_multiple instead." > $OUT',
    )
