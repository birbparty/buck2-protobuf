#!/usr/bin/env python3
"""Custom validation rule to check package naming conventions.

This script validates that protobuf package names follow organization standards:
- Must follow pattern: org.domain.service
- Must not use reserved words
- Must use lowercase with dots as separators
"""

import re
import sys
import json
from pathlib import Path


def validate_package_name(package_name):
    """Validate a protobuf package name against organization standards."""
    errors = []
    warnings = []
    
    if not package_name:
        errors.append("Package name is required")
        return errors, warnings
    
    # Check basic pattern: org.domain.service
    pattern = r'^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$'
    if not re.match(pattern, package_name):
        errors.append(f"Package name '{package_name}' must follow pattern 'org.domain.service' with lowercase letters and dots")
    
    # Check for reserved words
    reserved_words = ['test', 'temp', 'example', 'proto', 'internal']
    parts = package_name.split('.')
    for part in parts:
        if part in reserved_words:
            warnings.append(f"Package part '{part}' is a reserved word and should be avoided")
    
    # Check minimum depth
    if len(parts) < 3:
        errors.append(f"Package name '{package_name}' should have at least 3 parts (org.domain.service)")
    
    # Check length limits
    if len(package_name) > 100:
        errors.append(f"Package name '{package_name}' is too long (max 100 characters)")
    
    for part in parts:
        if len(part) > 20:
            warnings.append(f"Package part '{part}' is very long (consider shorter names)")
    
    return errors, warnings


def parse_proto_file(proto_file):
    """Parse a proto file to extract package information."""
    try:
        with open(proto_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract package declaration
        package_pattern = r'^\s*package\s+([a-zA-Z0-9_.]+)\s*;'
        matches = re.findall(package_pattern, content, re.MULTILINE)
        
        if not matches:
            return None, ["No package declaration found"]
        
        if len(matches) > 1:
            return matches[0], ["Multiple package declarations found"]
        
        return matches[0], []
        
    except Exception as e:
        return None, [f"Error reading proto file: {e}"]


def main():
    """Main validation function."""
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: check_package_naming.py <proto_file> [proto_file...]"
        }))
        sys.exit(1)
    
    results = {
        "rule_name": "Package Naming Convention",
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
        package_name, parse_errors = parse_proto_file(file_path)
        
        # Add parse errors
        for error in parse_errors:
            results["violations"].append({
                "file": proto_file,
                "severity": "error",
                "message": error
            })
            results["total_errors"] += 1
        
        # Validate package name if found
        if package_name:
            errors, warnings = validate_package_name(package_name)
            
            # Add validation errors
            for error in errors:
                results["violations"].append({
                    "file": proto_file,
                    "package": package_name,
                    "severity": "error",
                    "message": error
                })
                results["total_errors"] += 1
            
            # Add validation warnings
            for warning in warnings:
                results["violations"].append({
                    "file": proto_file,
                    "package": package_name,
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
