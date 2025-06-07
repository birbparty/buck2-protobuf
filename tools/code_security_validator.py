#!/usr/bin/env python3
"""
Generated code security validator for protobuf Buck2 integration.

This tool validates generated protobuf code for security vulnerabilities
and potential injection attacks across different programming languages.
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set


class CodeSecurityValidator:
    """Validates generated code for security issues."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the code security validator.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        
        # Security patterns for different languages
        self.security_patterns = {
            "python": [
                # Code injection patterns
                r'eval\s*\(',
                r'exec\s*\(',
                r'compile\s*\(',
                r'__import__\s*\(',
                
                # File system access
                r'open\s*\([\'"][^\'"]*/etc/',
                r'open\s*\([\'"][^\'"]*/proc/',
                
                # Network access
                r'urllib\.request\.',
                r'socket\.',
                r'requests\.',
                
                # Dangerous built-ins
                r'globals\s*\(\)',
                r'locals\s*\(\)',
                r'vars\s*\(',
            ],
            "go": [
                # Code execution
                r'exec\.Command',
                r'os\.Exec',
                r'syscall\.Exec',
                
                # File system access
                r'os\.Open\s*\(\s*[\'"][^\'"]*/etc/',
                r'ioutil\.ReadFile\s*\(\s*[\'"][^\'"]*/proc/',
                
                # Network access
                r'net\.Dial',
                r'http\.Get',
                r'http\.Post',
                
                # Unsafe operations
                r'unsafe\.',
                r'reflect\.UnsafeAddr',
            ],
            "typescript": [
                # Code execution
                r'eval\s*\(',
                r'Function\s*\(',
                r'setTimeout\s*\([\'"][^\'"]*[\'"]',
                r'setInterval\s*\([\'"][^\'"]*[\'"]',
                
                # DOM manipulation (XSS)
                r'innerHTML\s*=',
                r'outerHTML\s*=',
                r'document\.write',
                
                # Network access
                r'XMLHttpRequest',
                r'fetch\s*\(',
                r'axios\.',
                
                # Node.js specific
                r'require\s*\([\'"]child_process[\'"]',
                r'require\s*\([\'"]fs[\'"]',
            ],
            "cpp": [
                # Memory management issues
                r'malloc\s*\(',
                r'free\s*\(',
                r'strcpy\s*\(',
                r'strcat\s*\(',
                r'gets\s*\(',
                r'sprintf\s*\(',
                
                # System calls
                r'system\s*\(',
                r'exec\w+\s*\(',
                
                # File operations
                r'fopen\s*\([\'"][^\'"]*/etc/',
                r'fopen\s*\([\'"][^\'"]*/proc/',
                
                # Pointer arithmetic
                r'\*\s*\([^)]*\)\s*\+',
                r'\[\s*[^]]*\s*\+[^]]*\]',
            ],
            "rust": [
                # Unsafe blocks
                r'unsafe\s*\{',
                
                # FFI
                r'extern\s+[\'"]C[\'"]',
                
                # File operations
                r'std::fs::File::open\s*\([\'"][^\'"]*/etc/',
                r'std::fs::read_to_string\s*\([\'"][^\'"]*/proc/',
                
                # Network
                r'std::net::TcpStream',
                r'std::net::UdpSocket',
                
                # Process
                r'std::process::Command',
            ],
        }
        
        # Compile patterns for efficiency
        self.compiled_patterns = {}
        for language, patterns in self.security_patterns.items():
            self.compiled_patterns[language] = [
                re.compile(pattern, re.IGNORECASE | re.MULTILINE)
                for pattern in patterns
            ]
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[code-security-validator] {message}", file=sys.stderr)
    
    def validate_python_code(self, content: str) -> List[Dict]:
        """
        Validate Python code for security issues.
        
        Args:
            content: Python code content
            
        Returns:
            List of security issues found
        """
        issues = []
        
        # Pattern-based validation
        for i, pattern in enumerate(self.compiled_patterns.get("python", [])):
            matches = pattern.finditer(content)
            for match in matches:
                issues.append({
                    "type": "dangerous_pattern",
                    "language": "python",
                    "pattern": self.security_patterns["python"][i],
                    "match": match.group(),
                    "line": content[:match.start()].count('\n') + 1,
                    "severity": "high",
                })
        
        # AST-based validation for more sophisticated checks
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            issues.append({
                                "type": "dangerous_function",
                                "language": "python",
                                "function": node.func.id,
                                "line": node.lineno,
                                "severity": "high",
                            })
                
                # Check for attribute access that might be dangerous
                if isinstance(node, ast.Attribute):
                    dangerous_attrs = ['__globals__', '__locals__', '__dict__']
                    if node.attr in dangerous_attrs:
                        issues.append({
                            "type": "dangerous_attribute",
                            "language": "python",
                            "attribute": node.attr,
                            "line": node.lineno,
                            "severity": "medium",
                        })
        
        except SyntaxError:
            # If we can't parse the code, that's suspicious too
            issues.append({
                "type": "parse_error",
                "language": "python",
                "error": "Code contains syntax errors",
                "severity": "medium",
            })
        
        return issues
    
    def validate_generic_code(self, content: str, language: str) -> List[Dict]:
        """
        Validate code using pattern matching for non-Python languages.
        
        Args:
            content: Code content
            language: Programming language
            
        Returns:
            List of security issues found
        """
        issues = []
        
        patterns = self.compiled_patterns.get(language, [])
        pattern_strings = self.security_patterns.get(language, [])
        
        for i, pattern in enumerate(patterns):
            matches = pattern.finditer(content)
            for match in matches:
                issues.append({
                    "type": "dangerous_pattern",
                    "language": language,
                    "pattern": pattern_strings[i],
                    "match": match.group(),
                    "line": content[:match.start()].count('\n') + 1,
                    "severity": self._get_pattern_severity(pattern_strings[i], language),
                })
        
        return issues
    
    def _get_pattern_severity(self, pattern: str, language: str) -> str:
        """
        Determine severity level for a matched pattern.
        
        Args:
            pattern: Regex pattern that matched
            language: Programming language
            
        Returns:
            Severity level: "high", "medium", or "low"
        """
        # High severity patterns
        high_severity = [
            r'eval\s*\(',
            r'exec\s*\(',
            r'system\s*\(',
            r'unsafe\s*\{',
            r'innerHTML\s*=',
        ]
        
        for high_pattern in high_severity:
            if pattern == high_pattern:
                return "high"
        
        # Medium severity for file/network access
        if any(keyword in pattern for keyword in ['/etc/', '/proc/', 'net\.', 'http\.']):
            return "medium"
        
        return "low"
    
    def validate_file_size(self, file_path: str) -> List[Dict]:
        """
        Check if generated file size is reasonable.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of size-related issues
        """
        issues = []
        
        try:
            file_size = Path(file_path).stat().st_size
            
            # Flag extremely large files (>10MB)
            if file_size > 10 * 1024 * 1024:
                issues.append({
                    "type": "large_file",
                    "file_path": file_path,
                    "size_bytes": file_size,
                    "severity": "medium",
                    "description": "Generated file is unusually large",
                })
            
            # Flag empty files
            if file_size == 0:
                issues.append({
                    "type": "empty_file",
                    "file_path": file_path,
                    "severity": "low",
                    "description": "Generated file is empty",
                })
        
        except Exception as e:
            issues.append({
                "type": "file_access_error",
                "file_path": file_path,
                "error": str(e),
                "severity": "medium",
            })
        
        return issues
    
    def validate_file(self, file_path: str, language: str) -> Dict:
        """
        Validate a single generated file for security issues.
        
        Args:
            file_path: Path to the file to validate
            language: Programming language of the file
            
        Returns:
            Dictionary containing validation results
        """
        issues = []
        
        try:
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Validate file size
            issues.extend(self.validate_file_size(file_path))
            
            # Validate code content based on language
            if language == "python":
                issues.extend(self.validate_python_code(content))
            else:
                issues.extend(self.validate_generic_code(content, language))
            
            # Categorize by severity
            high_severity = [issue for issue in issues if issue.get("severity") == "high"]
            medium_severity = [issue for issue in issues if issue.get("severity") == "medium"]
            low_severity = [issue for issue in issues if issue.get("severity") == "low"]
            
            return {
                "file_path": file_path,
                "language": language,
                "issues": issues,
                "high_severity_count": len(high_severity),
                "medium_severity_count": len(medium_severity),
                "low_severity_count": len(low_severity),
                "total_issues": len(issues),
                "passed": len(high_severity) == 0,  # Pass if no high severity issues
                "high_severity_issues": high_severity,
                "medium_severity_issues": medium_severity,
                "low_severity_issues": low_severity,
            }
        
        except Exception as e:
            return {
                "file_path": file_path,
                "language": language,
                "error": f"Failed to validate file: {e}",
                "passed": False,
            }
    
    def validate_multiple_files(self, file_paths: List[str], language: str) -> Dict:
        """
        Validate multiple generated files for security issues.
        
        Args:
            file_paths: List of file paths to validate
            language: Programming language of the files
            
        Returns:
            Dictionary containing comprehensive validation results
        """
        all_results = []
        overall_issues = []
        
        for file_path in file_paths:
            result = self.validate_file(file_path, language)
            all_results.append(result)
            
            if "issues" in result:
                overall_issues.extend(result["issues"])
        
        # Calculate overall statistics
        high_severity_count = sum(result.get("high_severity_count", 0) for result in all_results)
        medium_severity_count = sum(result.get("medium_severity_count", 0) for result in all_results)
        low_severity_count = sum(result.get("low_severity_count", 0) for result in all_results)
        
        return {
            "language": language,
            "file_count": len(file_paths),
            "file_results": all_results,
            "overall_issues": overall_issues,
            "high_severity_count": high_severity_count,
            "medium_severity_count": medium_severity_count,
            "low_severity_count": low_severity_count,
            "total_issues": len(overall_issues),
            "passed": high_severity_count == 0,
            "files_passed": sum(1 for result in all_results if result.get("passed", False)),
            "files_failed": sum(1 for result in all_results if not result.get("passed", True)),
        }


def main():
    """Main entry point for code security validator."""
    parser = argparse.ArgumentParser(description="Validate generated code for security issues")
    parser.add_argument("--language", required=True, help="Programming language of the code")
    parser.add_argument("--input", action="append", required=True, help="Input file path (can be repeated)")
    parser.add_argument("--output", required=True, help="Output security report file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        validator = CodeSecurityValidator(verbose=args.verbose)
        
        # Validate files
        result = validator.validate_multiple_files(args.input, args.language)
        
        # Add metadata
        result["validator_version"] = "1.0.0"
        result["scan_timestamp"] = "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        
        # Write results to output file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Exit with appropriate code
        if result.get("passed", False):
            if args.verbose:
                print(f"Code security validation PASSED for {args.language}", file=sys.stderr)
                print(f"Files validated: {result['file_count']}", file=sys.stderr)
                if result.get("total_issues", 0) > 0:
                    print(f"Issues found: {result['total_issues']} "
                          f"(high: {result['high_severity_count']}, "
                          f"medium: {result['medium_severity_count']}, "
                          f"low: {result['low_severity_count']})", file=sys.stderr)
            sys.exit(0)
        else:
            if args.verbose:
                print(f"Code security validation FAILED for {args.language}", file=sys.stderr)
                print(f"High severity issues: {result.get('high_severity_count', 0)}", file=sys.stderr)
            sys.exit(1)
    
    except Exception as e:
        print(f"ERROR: Code security validation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
