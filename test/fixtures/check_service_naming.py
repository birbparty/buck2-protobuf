#!/usr/bin/env python3
"""Custom validation rule to check gRPC service naming conventions.

This script validates that gRPC service names follow organization standards:
- Must end with 'Service' suffix
- Must use PascalCase naming
- Must not have redundant naming patterns
"""

import re
import sys
import json
from pathlib import Path


def validate_service_name(service_name):
    """Validate a gRPC service name against organization standards."""
    errors = []
    warnings = []
    
    if not service_name:
        errors.append("Service name cannot be empty")
        return errors, warnings
    
    # Check for 'Service' suffix
    if not service_name.endswith('Service'):
        errors.append(f"Service name '{service_name}' must end with 'Service' suffix")
    
    # Check PascalCase pattern
    pascal_case_pattern = r'^[A-Z][a-zA-Z0-9]*Service$'
    if not re.match(pascal_case_pattern, service_name):
        errors.append(f"Service name '{service_name}' must use PascalCase (e.g., UserManagementService)")
    
    # Check for redundant patterns
    redundant_patterns = ['ServiceService', 'APIService', 'ApiService']
    for pattern in redundant_patterns:
        if pattern in service_name:
            warnings.append(f"Service name '{service_name}' contains redundant pattern '{pattern}'")
    
    # Check length limits
    if len(service_name) > 50:
        warnings.append(f"Service name '{service_name}' is very long (consider shorter name)")
    
    if len(service_name) < 8:  # Minimum: XService
        warnings.append(f"Service name '{service_name}' is very short (consider more descriptive name)")
    
    # Check for common anti-patterns
    anti_patterns = ['UtilService', 'HelperService', 'CommonService', 'BaseService']
    if service_name in anti_patterns:
        warnings.append(f"Service name '{service_name}' follows anti-pattern (use more specific name)")
    
    return errors, warnings


def validate_rpc_name(rpc_name, service_name):
    """Validate an RPC method name."""
    errors = []
    warnings = []
    
    if not rpc_name:
        errors.append("RPC name cannot be empty")
        return errors, warnings
    
    # Check PascalCase pattern
    pascal_case_pattern = r'^[A-Z][a-zA-Z0-9]*$'
    if not re.match(pascal_case_pattern, rpc_name):
        errors.append(f"RPC name '{rpc_name}' must use PascalCase")
    
    # Check for verb prefixes (recommended)
    verb_prefixes = ['Get', 'List', 'Create', 'Update', 'Delete', 'Search', 'Find', 'Validate', 'Process']
    has_verb_prefix = any(rpc_name.startswith(verb) for verb in verb_prefixes)
    if not has_verb_prefix:
        warnings.append(f"RPC name '{rpc_name}' should start with a verb (Get, Create, Update, etc.)")
    
    # Check length
    if len(rpc_name) > 40:
        warnings.append(f"RPC name '{rpc_name}' is very long")
    
    return errors, warnings


def parse_proto_file(proto_file):
    """Parse a proto file to extract service and RPC information."""
    try:
        with open(proto_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        services = []
        errors = []
        
        # Find all service definitions
        service_pattern = r'service\s+(\w+)\s*\{([^}]+)\}'
        service_matches = re.findall(service_pattern, content, re.MULTILINE | re.DOTALL)
        
        for service_name, service_body in service_matches:
            service_info = {
                'name': service_name,
                'rpcs': []
            }
            
            # Find RPC methods in the service
            rpc_pattern = r'rpc\s+(\w+)\s*\([^)]*\)\s*returns\s*\([^)]*\)'
            rpc_matches = re.findall(rpc_pattern, service_body)
            
            for rpc_name in rpc_matches:
                service_info['rpcs'].append(rpc_name)
            
            services.append(service_info)
        
        return services, errors
        
    except Exception as e:
        return [], [f"Error reading proto file: {e}"]


def main():
    """Main validation function."""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: check_service_naming.py <proto_file> [proto_file...]"
        }))
        sys.exit(1)
    
    results = {
        "rule_name": "Service Naming Convention",
        "files_checked": [],
        "total_errors": 0,
        "total_warnings": 0,
        "violations": []
    }
    
    for proto_file in sys.argv[1:]:
        file_path = Path(proto_file)
        if not file_path.exists():
            results["violations"].append({
                "file": proto_file,
                "severity": "error",
                "message": f"Proto file not found: {proto_file}"
            })
            results["total_errors"] += 1
            continue
        
        results["files_checked"].append(proto_file)
        
        # Parse the proto file
        services, parse_errors = parse_proto_file(file_path)
        
        # Add parse errors
        for error in parse_errors:
            results["violations"].append({
                "file": proto_file,
                "severity": "error",
                "message": error
            })
            results["total_errors"] += 1
        
        # Validate each service
        for service in services:
            service_name = service['name']
            
            # Validate service name
            errors, warnings = validate_service_name(service_name)
            
            for error in errors:
                results["violations"].append({
                    "file": proto_file,
                    "service": service_name,
                    "severity": "error",
                    "message": error
                })
                results["total_errors"] += 1
            
            for warning in warnings:
                results["violations"].append({
                    "file": proto_file,
                    "service": service_name,
                    "severity": "warning",
                    "message": warning
                })
                results["total_warnings"] += 1
            
            # Validate RPC names
            for rpc_name in service['rpcs']:
                rpc_errors, rpc_warnings = validate_rpc_name(rpc_name, service_name)
                
                for error in rpc_errors:
                    results["violations"].append({
                        "file": proto_file,
                        "service": service_name,
                        "rpc": rpc_name,
                        "severity": "error",
                        "message": error
                    })
                    results["total_errors"] += 1
                
                for warning in rpc_warnings:
                    results["violations"].append({
                        "file": proto_file,
                        "service": service_name,
                        "rpc": rpc_name,
                        "severity": "warning",
                        "message": warning
                    })
                    results["total_warnings"] += 1
    
    # Output results as JSON
    print(json.dumps(results, indent=2))
    
    # Exit with non-zero code if there are errors
    if results["total_errors"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
