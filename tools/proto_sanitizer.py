#!/usr/bin/env python3
"""
Proto input sanitizer for protobuf Buck2 integration.

This tool sanitizes proto file content to prevent injection attacks and
validates proto files for potentially dangerous constructs.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


class ProtoSanitizer:
    """Handles sanitization and validation of proto file inputs."""
    
    def __init__(self, max_depth: int = 10, max_imports: int = 100, verbose: bool = False):
        """
        Initialize the proto sanitizer.
        
        Args:
            max_depth: Maximum nesting depth allowed
            max_imports: Maximum number of imports allowed
            verbose: Enable verbose logging
        """
        self.max_depth = max_depth
        self.max_imports = max_imports
        self.verbose = verbose
        
        # Dangerous patterns that should be rejected or sanitized
        self.dangerous_patterns = [
            # Path traversal attempts
            r'\.\./.*',
            r'/\.\./.*',
            r'\\\.\.\\.*',
            
            # Suspicious import paths
            r'file://.*',
            r'https?://.*',
            r'ftp://.*',
            
            # System file paths
            r'/etc/.*',
            r'/proc/.*',
            r'/sys/.*',
            r'C:\\Windows\\.*',
            r'C:\\System32\\.*',
            
            # Extremely long identifiers (potential buffer overflow)
            r'[a-zA-Z_][a-zA-Z0-9_]{1000,}',
            
            # Nested message depths that could cause stack overflow
            r'(\s*message\s+\w+\s*\{[^}]*){15,}',
        ]
        
        # Compile patterns for efficiency
        self.compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.dangerous_patterns]
        
        # Allowed import patterns (whitelist approach)
        self.allowed_import_patterns = [
            r'google/protobuf/.*\.proto',
            r'[a-zA-Z_][a-zA-Z0-9_/]*\.proto',
        ]
        self.compiled_allowed_imports = [re.compile(pattern) for pattern in self.allowed_import_patterns]
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[proto-sanitizer] {message}", file=sys.stderr)
    
    def check_dangerous_patterns(self, content: str) -> List[Dict]:
        """
        Check for dangerous patterns in proto content.
        
        Args:
            content: Proto file content to check
            
        Returns:
            List of detected security issues
        """
        issues = []
        
        for i, pattern in enumerate(self.compiled_patterns):
            matches = pattern.finditer(content)
            for match in matches:
                issues.append({
                    "type": "dangerous_pattern",
                    "pattern_index": i,
                    "pattern": self.dangerous_patterns[i],
                    "match": match.group(),
                    "line": content[:match.start()].count('\n') + 1,
                    "severity": "high",
                })
        
        return issues
    
    def validate_imports(self, content: str) -> List[Dict]:
        """
        Validate import statements in proto content.
        
        Args:
            content: Proto file content to check
            
        Returns:
            List of import validation issues
        """
        issues = []
        import_pattern = re.compile(r'import\s+["\']([^"\']+)["\'];?', re.IGNORECASE)
        imports = import_pattern.findall(content)
        
        if len(imports) > self.max_imports:
            issues.append({
                "type": "too_many_imports",
                "count": len(imports),
                "max_allowed": self.max_imports,
                "severity": "medium",
            })
        
        for import_path in imports:
            # Check if import is in allowed patterns
            allowed = False
            for allowed_pattern in self.compiled_allowed_imports:
                if allowed_pattern.match(import_path):
                    allowed = True
                    break
            
            if not allowed:
                issues.append({
                    "type": "suspicious_import",
                    "import_path": import_path,
                    "severity": "high",
                })
        
        return issues
    
    def validate_nesting_depth(self, content: str) -> List[Dict]:
        """
        Validate message nesting depth to prevent stack overflow.
        
        Args:
            content: Proto file content to check
            
        Returns:
            List of nesting depth issues
        """
        issues = []
        lines = content.split('\n')
        depth = 0
        max_depth_seen = 0
        
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            
            # Count opening braces
            if 'message' in stripped and '{' in stripped:
                depth += 1
                max_depth_seen = max(max_depth_seen, depth)
            elif stripped == '}':
                depth = max(0, depth - 1)
        
        if max_depth_seen > self.max_depth:
            issues.append({
                "type": "excessive_nesting",
                "max_depth_seen": max_depth_seen,
                "max_allowed": self.max_depth,
                "severity": "medium",
            })
        
        return issues
    
    def validate_field_names(self, content: str) -> List[Dict]:
        """
        Validate field names for potential security issues.
        
        Args:
            content: Proto file content to check
            
        Returns:
            List of field name issues
        """
        issues = []
        
        # Pattern to match field definitions
        field_pattern = re.compile(r'^\s*(\w+)\s+(\w+)\s*=\s*\d+', re.MULTILINE)
        matches = field_pattern.finditer(content)
        
        for match in matches:
            field_type = match.group(1)
            field_name = match.group(2)
            
            # Check for extremely long field names
            if len(field_name) > 100:
                issues.append({
                    "type": "long_field_name",
                    "field_name": field_name,
                    "length": len(field_name),
                    "line": content[:match.start()].count('\n') + 1,
                    "severity": "low",
                })
            
            # Check for suspicious field names
            suspicious_names = ['__proto__', 'constructor', 'prototype', 'eval', 'exec']
            if field_name.lower() in suspicious_names:
                issues.append({
                    "type": "suspicious_field_name",
                    "field_name": field_name,
                    "line": content[:match.start()].count('\n') + 1,
                    "severity": "medium",
                })
        
        return issues
    
    def sanitize_content(self, content: str) -> str:
        """
        Sanitize proto content by removing or replacing dangerous constructs.
        
        Args:
            content: Original proto content
            
        Returns:
            Sanitized proto content
        """
        sanitized = content
        
        # Remove comments that might contain malicious content
        # But preserve important documentation
        sanitized = re.sub(r'//.*(?=\n)', '', sanitized)
        sanitized = re.sub(r'/\*.*?\*/', '', sanitized, flags=re.DOTALL)
        
        # Normalize whitespace to prevent certain injection techniques
        sanitized = re.sub(r'\s+', ' ', sanitized)
        sanitized = re.sub(r'\s*{\s*', ' {\n', sanitized)
        sanitized = re.sub(r'\s*}\s*', '\n}\n', sanitized)
        
        # Remove any null bytes or other control characters
        sanitized = ''.join(char for char in sanitized if ord(char) >= 32 or char in '\n\t')
        
        return sanitized
    
    def comprehensive_validation(self, content: str) -> Dict:
        """
        Perform comprehensive validation of proto content.
        
        Args:
            content: Proto file content to validate
            
        Returns:
            Dictionary containing validation results
        """
        all_issues = []
        
        # Check for dangerous patterns
        all_issues.extend(self.check_dangerous_patterns(content))
        
        # Validate imports
        all_issues.extend(self.validate_imports(content))
        
        # Validate nesting depth
        all_issues.extend(self.validate_nesting_depth(content))
        
        # Validate field names
        all_issues.extend(self.validate_field_names(content))
        
        # Categorize issues by severity
        high_severity = [issue for issue in all_issues if issue.get("severity") == "high"]
        medium_severity = [issue for issue in all_issues if issue.get("severity") == "medium"]
        low_severity = [issue for issue in all_issues if issue.get("severity") == "low"]
        
        return {
            "issues": all_issues,
            "high_severity_count": len(high_severity),
            "medium_severity_count": len(medium_severity),
            "low_severity_count": len(low_severity),
            "total_issues": len(all_issues),
            "passed": len(high_severity) == 0,  # Pass if no high severity issues
            "high_severity_issues": high_severity,
            "medium_severity_issues": medium_severity,
            "low_severity_issues": low_severity,
        }
    
    def sanitize_file(self, input_path: str, output_path: str) -> Dict:
        """
        Sanitize a proto file and write the result.
        
        Args:
            input_path: Path to input proto file
            output_path: Path to output sanitized proto file
            
        Returns:
            Dictionary containing sanitization results
        """
        try:
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # Validate original content
            validation_result = self.comprehensive_validation(original_content)
            
            # If high severity issues found, reject the file
            if validation_result["high_severity_count"] > 0:
                return {
                    "sanitized": False,
                    "error": "High severity security issues found",
                    "validation_result": validation_result,
                }
            
            # Sanitize content
            sanitized_content = self.sanitize_content(original_content)
            
            # Write sanitized file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(sanitized_content)
            
            self.log(f"Proto file sanitized: {input_path} -> {output_path}")
            
            return {
                "sanitized": True,
                "input_path": input_path,
                "output_path": output_path,
                "validation_result": validation_result,
                "changes_made": original_content != sanitized_content,
            }
        
        except Exception as e:
            return {
                "sanitized": False,
                "error": f"Failed to sanitize file: {e}",
                "input_path": input_path,
                "output_path": output_path,
            }


def main():
    """Main entry point for proto sanitizer."""
    parser = argparse.ArgumentParser(description="Sanitize proto file inputs for security")
    parser.add_argument("--input", required=True, help="Input proto file path")
    parser.add_argument("--output", required=True, help="Output sanitized proto file path")
    parser.add_argument("--max-depth", type=int, default=10, help="Maximum nesting depth")
    parser.add_argument("--max-imports", type=int, default=100, help="Maximum number of imports")
    parser.add_argument("--report", help="Output validation report to file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        sanitizer = ProtoSanitizer(
            max_depth=args.max_depth,
            max_imports=args.max_imports,
            verbose=args.verbose
        )
        
        # Sanitize the file
        result = sanitizer.sanitize_file(args.input, args.output)
        
        # Write report if requested
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_path, 'w') as f:
                json.dump(result, f, indent=2)
        
        # Exit with appropriate code
        if result.get("sanitized", False):
            if args.verbose:
                print(f"Proto sanitization PASSED: {args.input}", file=sys.stderr)
                validation = result.get("validation_result", {})
                if validation.get("total_issues", 0) > 0:
                    print(f"Issues found: {validation['total_issues']} "
                          f"(high: {validation['high_severity_count']}, "
                          f"medium: {validation['medium_severity_count']}, "
                          f"low: {validation['low_severity_count']})", file=sys.stderr)
            sys.exit(0)
        else:
            if args.verbose:
                print(f"Proto sanitization FAILED: {args.input}", file=sys.stderr)
                if "error" in result:
                    print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
    
    except Exception as e:
        print(f"ERROR: Proto sanitization failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
