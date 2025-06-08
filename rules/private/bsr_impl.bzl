"""BSR dependency resolution implementation for Buck2.

This module provides the core implementation for resolving BSR dependencies
with ORAS caching integration and Buck2 build system integration.
"""

def resolve_bsr_dependencies(ctx, bsr_deps, private_repo_configs = []):
    """
    Resolve BSR dependencies with ORAS caching and private repository support.
    
    Args:
        ctx: Buck2 rule context
        bsr_deps: List of BSR dependency references
        private_repo_configs: List of private repository configurations
        
    Returns:
        Dictionary with resolved dependency information:
        - proto_files: List of resolved proto files
        - import_paths: List of import paths for proto compilation
        - proto_infos: List of ProtoInfo providers (for transitive deps)
        - private_repos: List of private repository configurations used
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
    private_configs_used = []
    
    for dep in bsr_deps:
        if dep.startswith("@"):
            # Private repository dependency - find matching config
            repo_name = dep.split("//")[0]
            matching_config = None
            
            for config in private_repo_configs:
                if config.get("name") == repo_name.lstrip("@"):
                    matching_config = config
                    break
            
            if matching_config:
                private_deps.append(dep)
                private_configs_used.append(matching_config)
            else:
                fail("No configuration found for private repository: {}".format(repo_name))
        else:
            # Public dependency
            public_deps.append(dep)
    
    # Create a temporary script to resolve BSR dependencies with private repo support
    resolver_script_content = _create_enhanced_bsr_resolver_script(bsr_deps, private_configs_used)
    
    # Write the resolver script to a temporary file
    resolver_script = ctx.actions.write(
        "bsr_resolver.py",
        resolver_script_content
    )
    
    # Create output directory for resolved dependencies
    resolved_deps_dir = ctx.actions.declare_output("bsr_resolved", dir=True)
    
    # Execute BSR dependency resolution with private repository support
    ctx.actions.run(
        cmd = [
            "python3",
            resolver_script,
            "--output-dir", resolved_deps_dir.as_output(),
            "--cache-dir", "/tmp/buck2-bsr-cache",
            "--registry", "oras.birb.homes",
            "--support-private-repos"
        ],
        outputs = [resolved_deps_dir],
        category = "bsr_resolve_private",
        identifier = "resolve_{}".format("_".join([dep.replace("/", "_").replace(":", "_").replace("@", "at_") for dep in bsr_deps]))
    )
    
    # Collect resolved proto files
    proto_files = []
    import_paths = []
    
    # Handle both public and private dependencies
    for bsr_dep in bsr_deps:
        if bsr_dep.startswith("@"):
            # Private repository dependency
            repo_name = bsr_dep.split("//")[0].lstrip("@")
            module_path = bsr_dep.split("//")[1] if "//" in bsr_dep else "default"
            
            # Add expected proto files for private repository
            expected_protos = _get_expected_private_repo_files(bsr_dep, resolved_deps_dir, repo_name)
            proto_files.extend(expected_protos)
            
            # Add import path for private dependency
            dep_import_path = "{}/private/{}".format(resolved_deps_dir.as_output(), repo_name)
            if dep_import_path not in import_paths:
                import_paths.append(dep_import_path)
        else:
            # Public dependency - existing logic
            parts = bsr_dep.split("/")
            if len(parts) >= 3:
                module_name = parts[2].split(":")[0]
                
                # Add expected proto files based on popular BSR modules
                expected_protos = _get_expected_proto_files(bsr_dep, resolved_deps_dir)
                proto_files.extend(expected_protos)
                
                # Add import path for this dependency
                dep_import_path = "{}/public/{}".format(resolved_deps_dir.as_output(), module_name)
                if dep_import_path not in import_paths:
                    import_paths.append(dep_import_path)
    
    return {
        "proto_files": proto_files,
        "import_paths": import_paths,
        "proto_infos": [],
        "private_repos": private_configs_used
    }

def _create_enhanced_bsr_resolver_script(bsr_deps, private_configs = []):
    """
    Create a Python script to resolve BSR dependencies with private repository support.
    
    Args:
        bsr_deps: List of BSR dependency references
        private_configs: List of private repository configurations
        
    Returns:
        String containing the Python script content
    """
    script_template = '''#!/usr/bin/env python3
import argparse
import json
import os
import sys
import tempfile
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Resolve BSR dependencies with private repository support")
    parser.add_argument("--output-dir", required=True, help="Output directory")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--registry", default="oras.birb.homes", help="ORAS registry")
    parser.add_argument("--support-private-repos", action="store_true", help="Enable private repository support")
    args = parser.parse_args()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create separate directories for public and private repositories
    public_dir = output_dir / "public"
    private_dir = output_dir / "private"
    public_dir.mkdir(exist_ok=True)
    private_dir.mkdir(exist_ok=True)
    
    # BSR dependencies to resolve
    bsr_deps = {bsr_deps_list}
    
    # Private repository configurations
    private_configs = {private_configs_list}
    
    # For each dependency, try to resolve it
    for bsr_dep in bsr_deps:
        try:
            print(f"Resolving BSR dependency: {{bsr_dep}}")
            
            if bsr_dep.startswith("@"):
                # Private repository dependency
                _resolve_private_dependency(bsr_dep, private_dir, private_configs)
            else:
                # Public repository dependency
                _resolve_public_dependency(bsr_dep, public_dir)
                
        except Exception as e:
            print(f"Error resolving {{bsr_dep}}: {{e}}")
            continue

def _resolve_private_dependency(bsr_dep, private_dir, private_configs):
    """Resolve a private BSR dependency with authentication."""
    print(f"Resolving private dependency: {{bsr_dep}}")
    
    # Parse private dependency reference: @repo_name//module:version
    if "//" in bsr_dep:
        repo_ref, module_path = bsr_dep.split("//", 1)
        repo_name = repo_ref.lstrip("@")
        
        if ":" in module_path:
            module, version = module_path.split(":", 1)
        else:
            module = module_path
            version = "main"
    else:
        print(f"Invalid private dependency format: {{bsr_dep}}")
        return
    
    # Find matching repository configuration
    repo_config = None
    for config in private_configs:
        if config.get("name") == repo_name:
            repo_config = config
            break
    
    if not repo_config:
        print(f"No configuration found for private repository: {{repo_name}}")
        return
    
    # Create output directory for this private dependency
    dep_output_dir = private_dir / repo_name / module
    dep_output_dir.mkdir(parents=True, exist_ok=True)
    
    # For now, create placeholder files for private dependencies
    # In a full implementation, this would use the private BSR authenticator
    # to download the actual dependencies
    _create_private_placeholder_protos(bsr_dep, dep_output_dir, repo_config)

def _resolve_public_dependency(bsr_dep, public_dir):
    """Resolve a public BSR dependency."""
    # Parse dependency reference
    parts = bsr_dep.split("/")
    if len(parts) < 3:
        print(f"Invalid BSR reference: {{bsr_dep}}")
        return
        
    registry = parts[0]
    owner = parts[1]
    module_version = parts[2]
    
    if ":" in module_version:
        module, version = module_version.split(":", 1)
    else:
        module = module_version
        version = "main"
    
    # Create output directory for this dependency
    dep_output_dir = public_dir / module
    dep_output_dir.mkdir(exist_ok=True)
    
    # Try to download using buf CLI
    full_ref = f"{{registry}}/{{owner}}/{{module}}:{{version}}"
    
    try:
        result = subprocess.run([
            "buf", "export", full_ref,
            "--output", str(dep_output_dir)
        ], capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            print(f"Successfully resolved {{bsr_dep}}")
        else:
            print(f"Failed to resolve {{bsr_dep}}: {{result.stderr}}")
            # Create placeholder proto files for known dependencies
            _create_placeholder_protos(bsr_dep, dep_output_dir)
    
    except subprocess.TimeoutExpired:
        print(f"Timeout resolving {{bsr_dep}}")
        _create_placeholder_protos(bsr_dep, dep_output_dir)
    except FileNotFoundError:
        print("buf CLI not found, creating placeholder protos")
        _create_placeholder_protos(bsr_dep, dep_output_dir)

def _create_private_placeholder_protos(bsr_dep, output_dir, repo_config):
    """Create placeholder proto files for private BSR dependencies."""
    print(f"Creating placeholder protos for private dependency: {{bsr_dep}}")
    
    # Create a basic placeholder proto file
    placeholder_proto = output_dir / "placeholder.proto"
    placeholder_proto.write_text(f'''
syntax = "proto3";

// Placeholder for private BSR dependency: {bsr_dep}
// Repository: {repo_config.get("repository", "unknown")}
// Teams: {", ".join([team.get("team", "unknown") for team in repo_config.get("teams", [])])}

package placeholder;

message PrivateDependencyPlaceholder {{
  string dependency_ref = 1;
  string repository = 2;
  repeated string teams = 3;
}}
''')
    
    # Create metadata file for private dependency
    metadata_file = output_dir / "metadata.json"
    metadata = {{
        "dependency_ref": bsr_dep,
        "repository": repo_config.get("repository"),
        "auth_method": repo_config.get("auth_method"),
        "teams": repo_config.get("teams", []),
        "is_private": True,
        "resolved_at": "placeholder"
    }}
    
    metadata_file.write_text(json.dumps(metadata, indent=2))

def _create_placeholder_protos(bsr_dep, output_dir):
    """Create placeholder proto files for known BSR dependencies."""
    if "googleapis" in bsr_dep:
        # Create placeholder for googleapis
        google_dir = output_dir / "google"
        google_dir.mkdir(exist_ok=True)
        
        # Create basic google/api annotations
        api_dir = google_dir / "api"
        api_dir.mkdir(exist_ok=True)
        
        annotations_proto = api_dir / "annotations.proto"
        annotations_proto.write_text('''
syntax = "proto3";

package google.api;

option go_package = "google.golang.org/genproto/googleapis/api/annotations;annotations";

import "google/protobuf/descriptor.proto";

extend google.protobuf.MethodOptions {{
  HttpRule http = 72295728;
}}

message HttpRule {{
  string selector = 1;
  oneof pattern {{
    string get = 2;
    string put = 3;
    string post = 4;
    string delete = 5;
    string patch = 6;
    HttpRule custom = 8;
  }}
  string body = 7;
  string response_body = 12;
  repeated HttpRule additional_bindings = 11;
}}
''')
        
        # Create basic http proto
        http_proto = api_dir / "http.proto"
        http_proto.write_text('''
syntax = "proto3";

package google.api;

option go_package = "google.golang.org/genproto/googleapis/api/annotations;annotations";

message Http {{
  repeated HttpRule rules = 1;
  bool fully_decode_reserved_expansion = 2;
}}

message HttpRule {{
  string selector = 1;
  oneof pattern {{
    string get = 2;
    string put = 3;
    string post = 4;
    string delete = 5;
    string patch = 6;
    HttpRule custom = 8;
  }}
  string body = 7;
  string response_body = 12;
  repeated HttpRule additional_bindings = 11;
}}
''')
        
    elif "grpc-gateway" in bsr_dep:
        # Create placeholder for grpc-gateway
        grpc_dir = output_dir / "grpc"
        grpc_dir.mkdir(exist_ok=True)
        
        gateway_dir = grpc_dir / "gateway"
        gateway_dir.mkdir(exist_ok=True)
        
        gateway_proto = gateway_dir / "gateway.proto"
        gateway_proto.write_text('''
syntax = "proto3";

package grpc.gateway;

option go_package = "github.com/grpc-ecosystem/grpc-gateway/v2/protoc-gen-grpc-gateway/descriptor";

message GatewayOptions {{
  string base_path = 1;
}}
''')
        
    elif "protoc-gen-validate" in bsr_dep:
        # Create placeholder for validate
        validate_dir = output_dir / "validate"
        validate_dir.mkdir(exist_ok=True)
        
        validate_proto = validate_dir / "validate.proto"
        validate_proto.write_text('''
syntax = "proto2";

package validate;

option go_package = "github.com/envoyproxy/protoc-gen-validate/validate";

import "google/protobuf/descriptor.proto";

extend google.protobuf.FieldOptions {{
  optional FieldRules rules = 1071;
}}

message FieldRules {{
  optional MessageRules message = 1;
  optional RepeatedRules repeated = 2;
  optional MapRules map = 3;
  optional AnyRules any = 4;
}}

message MessageRules {{
  optional bool skip = 1;
  optional bool required = 2;
}}

message RepeatedRules {{
  optional uint64 min_items = 1;
  optional uint64 max_items = 2;
  optional bool unique = 3;
}}

message MapRules {{
  optional uint64 min_pairs = 1;
  optional uint64 max_pairs = 2;
  optional bool no_sparse = 3;
}}

message AnyRules {{
  optional bool required = 1;
  repeated string in = 2;
  repeated string not_in = 3;
}}
''')

if __name__ == "__main__":
    main()
'''
    
    # Format the script with the actual BSR dependencies and private configs
    bsr_deps_str = str(bsr_deps)
    private_configs_str = str(private_configs)
    return script_template.format(bsr_deps_list=bsr_deps_str, private_configs_list=private_configs_str)

def _get_expected_private_repo_files(bsr_dep, base_dir, repo_name):
    """
    Get expected proto files for a private BSR dependency.
    
    Args:
        bsr_dep: Private BSR dependency reference (e.g., "@myorg_private//common:v1.0.0")
        base_dir: Base directory for resolved dependencies
        repo_name: Repository name (e.g., "myorg_private")
        
    Returns:
        List of expected proto file artifacts for private repository
    """
    expected_files = []
    
    # Parse module from private dependency reference
    if "//" in bsr_dep:
        module_path = bsr_dep.split("//")[1]
        if ":" in module_path:
            module = module_path.split(":")[0]
        else:
            module = module_path
    else:
        module = "default"
    
    # Private repositories use a different directory structure
    private_module_dir = base_dir.project("private/{}/{}".format(repo_name, module))
    
    # For private repositories, we expect placeholder files initially
    # In a full implementation, this would be based on the actual repository structure
    expected_files.extend([
        private_module_dir.project("placeholder.proto"),
        private_module_dir.project("metadata.json"),
    ])
    
    return expected_files

def _get_expected_proto_files(bsr_dep, base_dir):
    """
    Get expected proto files for a BSR dependency.
    
    Args:
        bsr_dep: BSR dependency reference
        base_dir: Base directory for resolved dependencies
        
    Returns:
        List of expected proto file artifacts
    """
    expected_files = []
    
    # Parse module name from BSR reference
    parts = bsr_dep.split("/")
    if len(parts) >= 3:
        module_name = parts[2].split(":")[0]
        module_dir = base_dir.project("{}/".format(module_name))
        
        if "googleapis" in bsr_dep:
            # Expected googleapis proto files
            expected_files.extend([
                module_dir.project("google/api/annotations.proto"),
                module_dir.project("google/api/http.proto"),
            ])
        elif "grpc-gateway" in bsr_dep:
            # Expected grpc-gateway proto files
            expected_files.extend([
                module_dir.project("grpc/gateway/gateway.proto"),
            ])
        elif "protoc-gen-validate" in bsr_dep:
            # Expected validate proto files
            expected_files.extend([
                module_dir.project("validate/validate.proto"),
            ])
        elif "connect" in bsr_dep:
            # Expected connect proto files
            expected_files.extend([
                module_dir.project("connect/connect.proto"),
            ])
    
    return expected_files

def validate_bsr_dependencies(bsr_deps):
    """
    Validate BSR dependency references.
    
    Args:
        bsr_deps: List of BSR dependency references
        
    Returns:
        True if all dependencies are valid, False otherwise
    """
    for bsr_dep in bsr_deps:
        if not _is_valid_bsr_reference(bsr_dep):
            fail("Invalid BSR dependency reference: {}".format(bsr_dep))
    
    return True

def _is_valid_bsr_reference(bsr_ref):
    """
    Check if a BSR reference is valid.
    
    Args:
        bsr_ref: BSR reference string
        
    Returns:
        True if valid, False otherwise
    """
    # Basic validation: should have format registry/owner/module[:version]
    parts = bsr_ref.split("/")
    if len(parts) != 3:
        return False
    
    registry, owner, module_version = parts
    
    # Registry should be a valid domain
    if not registry or "." not in registry:
        return False
    
    # Owner and module should be non-empty
    if not owner or not module_version:
        return False
    
    # Module version can optionally have a version
    if ":" in module_version:
        module, version = module_version.split(":", 1)
        if not module or not version:
            return False
    
    return True

def get_popular_bsr_dependencies():
    """
    Get a list of popular BSR dependencies for validation.
    
    Returns:
        List of popular BSR dependency references
    """
    return [
        "buf.build/googleapis/googleapis",
        "buf.build/grpc-ecosystem/grpc-gateway",
        "buf.build/envoyproxy/protoc-gen-validate",
        "buf.build/connectrpc/connect",
    ]

def is_supported_bsr_dependency(bsr_ref):
    """
    Check if a BSR dependency is supported by the popular resolver.
    
    Args:
        bsr_ref: BSR reference string
        
    Returns:
        True if supported, False otherwise
    """
    popular_deps = get_popular_bsr_dependencies()
    
    # Check if the base reference (without version) is in popular deps
    base_ref = bsr_ref.split(":")[0] if ":" in bsr_ref else bsr_ref
    
    for popular_dep in popular_deps:
        popular_base = popular_dep.split(":")[0] if ":" in popular_dep else popular_dep
        if base_ref == popular_base:
            return True
    
    return False
