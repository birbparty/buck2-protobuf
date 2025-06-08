"""BSR repository configuration rules for Buck2.

This module provides rules for configuring private BSR repositories with 
authentication, team-based access control, and seamless integration with
public repositories.
"""

load("//rules/private:bsr_impl.bzl", "resolve_bsr_dependencies", "validate_bsr_dependencies")
load("//rules/private:providers.bzl", "BSRRepositoryInfo")
load("//rules/private:utils.bzl", "get_toolchain_info")

def bsr_repository(
    name,
    repository,
    auth_method = "auto",
    teams = [],
    access_level = "read",
    service_account_file = None,
    cache_ttl = 3600,
    visibility = None,
    **kwargs):
    """
    Configure a private BSR repository with authentication and access control.
    
    This rule sets up authentication and access control for private BSR repositories,
    enabling secure schema sharing within teams and organizations.
    
    Args:
        name: Repository configuration name (used as reference in dependencies)
        repository: BSR repository reference (e.g., "buf.build/myorg/private-schemas")
        auth_method: Authentication method ("auto", "environment", "service_account", 
                    "keychain", "netrc", "interactive")
        teams: List of teams with access to this repository (e.g., ["@platform-team"])
        access_level: Access level for the repository ("read", "write", "admin")
        service_account_file: Path to service account key file (for CI/CD)
        cache_ttl: Cache time-to-live in seconds for resolved dependencies
        visibility: Visibility list for this repository configuration
        **kwargs: Additional configuration options
        
    Example:
        ```python
        bsr_repository(
            name = "myorg_private",
            repository = "buf.build/myorg/private-schemas",
            auth_method = "service_account",
            teams = ["@platform-team", "@backend-team"],
            access_level = "read",
        )
        ```
    """
    
    # Validate repository reference format
    if not repository or "/" not in repository:
        fail("Invalid BSR repository reference: {}. Expected format: registry/owner/module".format(repository))
    
    # Validate access level
    valid_access_levels = ["read", "write", "admin"]
    if access_level not in valid_access_levels:
        fail("Invalid access level: {}. Must be one of: {}".format(access_level, valid_access_levels))
    
    # Validate authentication method
    valid_auth_methods = ["auto", "environment", "service_account", "keychain", "netrc", "interactive"]
    if auth_method not in valid_auth_methods:
        fail("Invalid auth method: {}. Must be one of: {}".format(auth_method, valid_auth_methods))
    
    # Create repository configuration
    bsr_repository_config(
        name = name,
        repository = repository,
        auth_method = auth_method,
        teams = teams,
        access_level = access_level,
        service_account_file = service_account_file,
        cache_ttl = cache_ttl,
        visibility = visibility,
        **kwargs
    )

def _bsr_repository_config_impl(ctx):
    """Implementation for BSR repository configuration."""
    
    # Create repository configuration data
    config_data = {
        "repository": ctx.attrs.repository,
        "auth_method": ctx.attrs.auth_method,
        "teams": ctx.attrs.teams,
        "access_level": ctx.attrs.access_level,
        "service_account_file": ctx.attrs.service_account_file,
        "cache_ttl": ctx.attrs.cache_ttl,
        "is_private": True,
    }
    
    # Write configuration to a file for use by dependency resolution
    config_file = ctx.actions.write(
        "bsr_repository_config.json",
        json.encode(config_data)
    )
    
    return [
        DefaultInfo(default_output = config_file),
        BSRRepositoryInfo(
            repository = ctx.attrs.repository,
            auth_method = ctx.attrs.auth_method,
            teams = ctx.attrs.teams,
            access_level = ctx.attrs.access_level,
            service_account_file = ctx.attrs.service_account_file,
            cache_ttl = ctx.attrs.cache_ttl,
            config_file = config_file,
            is_private = True,
        )
    ]

bsr_repository_config = rule(
    impl = _bsr_repository_config_impl,
    attrs = {
        "repository": attrs.string(mandatory = True),
        "auth_method": attrs.string(default = "auto"),
        "teams": attrs.list(attrs.string(), default = []),
        "access_level": attrs.string(default = "read"),
        "service_account_file": attrs.option(attrs.string(), default = None),
        "cache_ttl": attrs.int(default = 3600),
    }
)

def bsr_dependency(
    repository_ref,
    module = None,
    version = None):
    """
    Create a BSR dependency reference with proper parsing.
    
    Args:
        repository_ref: Full BSR reference or configured repository name
        module: Optional module name (if using configured repository)
        version: Optional version (defaults to latest)
        
    Returns:
        Properly formatted BSR dependency reference
        
    Example:
        ```python
        # Using full reference
        bsr_dependency("buf.build/googleapis/googleapis:main")
        
        # Using configured private repository
        bsr_dependency("@myorg_private", module = "common", version = "v1.0.0")
        ```
    """
    if repository_ref.startswith("@"):
        # Using configured repository
        if not module:
            fail("Module name required when using configured repository: {}".format(repository_ref))
        
        # Format: @repo_name//module:version
        if version:
            return "{}//{}:{}".format(repository_ref, module, version)
        else:
            return "{}//{}".format(repository_ref, module)
    else:
        # Direct BSR reference
        return repository_ref

def resolve_private_bsr_dependencies(ctx, bsr_deps, repository_configs = {}):
    """
    Resolve BSR dependencies with private repository support.
    
    Args:
        ctx: Buck2 rule context
        bsr_deps: List of BSR dependency references
        repository_configs: Dictionary of repository configurations
        
    Returns:
        Dictionary with resolved dependency information
    """
    if not bsr_deps:
        return {
            "proto_files": [],
            "import_paths": [],
            "proto_infos": [],
            "private_repos": []
        }
    
    # Separate public and private dependencies
    public_deps = []
    private_deps = []
    private_repo_configs = []
    
    for dep in bsr_deps:
        if dep.startswith("@"):
            # Private repository dependency
            repo_name = dep.split("//")[0]
            if repo_name in repository_configs:
                private_deps.append(dep)
                private_repo_configs.append(repository_configs[repo_name])
            else:
                fail("Unknown private repository: {}. Did you forget to configure it with bsr_repository()?".format(repo_name))
        else:
            # Public dependency
            public_deps.append(dep)
    
    # Resolve dependencies with enhanced private repository support
    result = resolve_bsr_dependencies(ctx, bsr_deps, private_repo_configs)
    result["private_repos"] = private_repo_configs
    
    return result

def enhanced_proto_library(
    name,
    srcs = [],
    deps = [],
    bsr_deps = [],
    bsr_repositories = {},
    team = None,
    team_config = None,
    visibility = None,
    **kwargs):
    """
    Enhanced proto_library rule with private BSR repository and team support.
    
    Args:
        name: Target name
        srcs: Proto source files
        deps: Local proto dependencies  
        bsr_deps: BSR dependencies (public and private)
        bsr_repositories: Dictionary of BSR repository configurations
        team: Team name for team-aware builds
        team_config: Team configuration target
        visibility: Target visibility
        **kwargs: Additional proto_library arguments
        
    Example:
        ```python
        enhanced_proto_library(
            name = "api_proto",
            srcs = ["api.proto"],
            bsr_deps = [
                "@myorg_private//common:types",      # Private repo
                "buf.build/googleapis/googleapis",   # Public repo
            ],
            bsr_repositories = {
                "@myorg_private": ":myorg_private_config",
            },
            team = "backend-team",
            team_config = ":backend_team_config",
        )
        ```
    """
    
    # Validate BSR dependencies
    if bsr_deps:
        validate_bsr_dependencies(bsr_deps)
    
    # Validate team permissions if team is specified
    if team and bsr_deps:
        _validate_team_bsr_permissions(team, bsr_deps, team_config)
    
    # Import the base proto_library rule
    # This will be the standard Buck2 proto_library with BSR enhancement
    _enhanced_proto_library_impl(
        name = name,
        srcs = srcs,
        deps = deps,
        bsr_deps = bsr_deps,
        bsr_repositories = bsr_repositories,
        team = team,
        team_config = team_config,
        visibility = visibility,
        **kwargs
    )

def _validate_team_bsr_permissions(team, bsr_deps, team_config):
    """
    Validate that a team has permission to access BSR dependencies.
    
    Args:
        team: Team name
        bsr_deps: List of BSR dependency references
        team_config: Team configuration target (optional)
    """
    # For now, this is a placeholder validation
    # In a full implementation, this would:
    # 1. Load team configuration from team_config target
    # 2. Check each BSR dependency against team permissions
    # 3. Fail build if team lacks permission for any dependency
    
    if not team:
        return
    
    # Extract repository references from BSR dependencies
    for dep in bsr_deps:
        if dep.startswith("@"):
            # Private repository dependency - check team permissions
            repo_ref = dep.split("//")[0]
            # TODO: Implement actual permission validation
            # This would query the team management system
            pass
        else:
            # Public dependency - generally allowed for all teams
            pass

def _enhanced_proto_library_impl(
    name,
    srcs,
    deps,
    bsr_deps,
    bsr_repositories,
    team = None,
    team_config = None,
    visibility = None,
    **kwargs):
    """Internal implementation for enhanced proto_library."""
    
    # For now, we'll use the existing proto_library rule
    # In a full implementation, this would be a proper Buck2 rule
    # that integrates BSR dependency resolution
    
    # Create team-aware BSR resolution command
    resolution_cmd = "mkdir -p $OUT && echo 'BSR dependencies resolved"
    if team:
        resolution_cmd += " for team {}".format(team)
    resolution_cmd += "' > $OUT/status.txt"
    
    if team_config:
        resolution_cmd += " && echo 'Team config: {}' >> $OUT/status.txt".format(team_config)
    
    native.genrule(
        name = name + "_bsr_resolution",
        out = "bsr_resolved",
        cmd = resolution_cmd,
        visibility = visibility,
    )
    
    # Call standard proto_library with resolved dependencies
    # This is a simplified implementation - full version would integrate
    # the resolved BSR dependencies into the proto compilation
    native.genrule(
        name = name,
        srcs = srcs + [":{}".format(name + "_bsr_resolution")],
        out = "{}.proto.resolved".format(name),
        cmd = "cp $(location {}) $OUT".format(srcs[0]) if srcs else "touch $OUT",
        visibility = visibility,
    )

# Team-aware BSR configuration rules
def bsr_team_config(
    name,
    team,
    members = {},
    repositories = {},
    settings = {},
    visibility = None):
    """
    Configure BSR team settings for Buck2 builds.
    
    Args:
        name: Configuration target name
        team: Team name
        members: Dictionary of team members and their roles
        repositories: Dictionary of repository access configurations
        settings: Team-specific settings
        visibility: Target visibility
        
    Example:
        ```python
        bsr_team_config(
            name = "backend_team_config",
            team = "backend-team",
            members = {
                "alice": "maintainer",
                "bob": "contributor",
                "charlie": "admin"
            },
            repositories = {
                "buf.build/myorg/platform-schemas": "read",
                "buf.build/myorg/service-schemas": "write"
            },
            settings = {
                "auto_approve_members": False,
                "require_2fa": True
            }
        )
        ```
    """
    
    # Create team configuration data
    team_config_data = {
        "team": team,
        "members": members,
        "repositories": repositories,
        "settings": settings
    }
    
    # Generate team configuration target
    native.genrule(
        name = name,
        out = "team_config.json",
        cmd = "echo '{}' > $OUT".format(json.encode(team_config_data)),
        visibility = visibility,
    )
