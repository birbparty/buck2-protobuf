#!/usr/bin/env python3
"""
Security validator for protobuf Buck2 integration.

This tool validates the integrity of protoc and plugin binaries using
SHA256 checksums to ensure they haven't been tampered with.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional


class SecurityValidator:
    """Handles security validation of tools and artifacts."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the security validator.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[security-validator] {message}", file=sys.stderr)
    
    def calculate_sha256(self, file_path: Path) -> str:
        """
        Calculate SHA256 hash of a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal SHA256 hash string
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def validate_tool_integrity(self, tool_path: str, expected_checksum: str) -> Dict:
        """
        Validates SHA256 checksum of a tool binary.
        
        Args:
            tool_path: Path to the tool binary
            expected_checksum: Expected SHA256 hash
            
        Returns:
            Dictionary containing validation results
        """
        tool_file = Path(tool_path)
        
        if not tool_file.exists():
            return {
                "valid": False,
                "error": f"Tool file does not exist: {tool_path}",
                "tool_path": tool_path,
                "expected_checksum": expected_checksum,
                "actual_checksum": None,
            }
        
        if not tool_file.is_file():
            return {
                "valid": False,
                "error": f"Tool path is not a file: {tool_path}",
                "tool_path": tool_path,
                "expected_checksum": expected_checksum,
                "actual_checksum": None,
            }
        
        try:
            actual_checksum = self.calculate_sha256(tool_file)
            
            if actual_checksum.lower() == expected_checksum.lower():
                self.log(f"Tool integrity validated: {tool_path}")
                return {
                    "valid": True,
                    "tool_path": tool_path,
                    "expected_checksum": expected_checksum,
                    "actual_checksum": actual_checksum,
                }
            else:
                self.log(f"Tool integrity validation failed: {tool_path}")
                self.log(f"Expected: {expected_checksum}")
                self.log(f"Actual:   {actual_checksum}")
                return {
                    "valid": False,
                    "error": "Checksum mismatch - tool may have been tampered with",
                    "tool_path": tool_path,
                    "expected_checksum": expected_checksum,
                    "actual_checksum": actual_checksum,
                }
        
        except Exception as e:
            return {
                "valid": False,
                "error": f"Failed to calculate checksum: {e}",
                "tool_path": tool_path,
                "expected_checksum": expected_checksum,
                "actual_checksum": None,
            }
    
    def check_executable_permissions(self, tool_path: str) -> bool:
        """
        Check if a tool has executable permissions.
        
        Args:
            tool_path: Path to the tool binary
            
        Returns:
            True if executable, False otherwise
        """
        return os.access(tool_path, os.X_OK)
    
    def validate_file_size(self, tool_path: str, min_size: int = 1024, max_size: int = 500 * 1024 * 1024) -> bool:
        """
        Validate file size is within reasonable bounds.
        
        Args:
            tool_path: Path to the tool binary
            min_size: Minimum expected file size in bytes
            max_size: Maximum expected file size in bytes
            
        Returns:
            True if size is valid, False otherwise
        """
        try:
            file_size = Path(tool_path).stat().st_size
            return min_size <= file_size <= max_size
        except:
            return False
    
    def comprehensive_tool_validation(self, tool_path: str, expected_checksum: str) -> Dict:
        """
        Performs comprehensive validation of a tool binary.
        
        Args:
            tool_path: Path to the tool binary
            expected_checksum: Expected SHA256 hash
            
        Returns:
            Dictionary containing comprehensive validation results
        """
        # Basic integrity validation
        integrity_result = self.validate_tool_integrity(tool_path, expected_checksum)
        
        # Additional security checks
        additional_checks = {
            "executable_permissions": self.check_executable_permissions(tool_path),
            "size_validation": self.validate_file_size(tool_path),
        }
        
        # Combine results
        result = {
            **integrity_result,
            "additional_checks": additional_checks,
            "overall_valid": (
                integrity_result["valid"] and
                additional_checks["executable_permissions"] and
                additional_checks["size_validation"]
            ),
        }
        
        return result


def main():
    """Main entry point for security validator."""
    parser = argparse.ArgumentParser(description="Validate tool security and integrity")
    parser.add_argument("--tool-path", required=True, help="Path to tool binary")
    parser.add_argument("--expected-checksum", required=True, help="Expected SHA256 checksum")
    parser.add_argument("--output", required=True, help="Output file for validation results")
    parser.add_argument("--comprehensive", action="store_true", 
                       help="Perform comprehensive validation (default: basic)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        validator = SecurityValidator(verbose=args.verbose)
        
        # Perform validation
        if args.comprehensive:
            result = validator.comprehensive_tool_validation(args.tool_path, args.expected_checksum)
        else:
            result = validator.validate_tool_integrity(args.tool_path, args.expected_checksum)
        
        # Add metadata
        result["validation_type"] = "comprehensive" if args.comprehensive else "basic"
        result["validator_version"] = "1.0.0"
        
        # Write results to output file
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(result, f, indent=2)
        
        # Exit with appropriate code
        if result.get("overall_valid", result.get("valid", False)):
            if args.verbose:
                print(f"Tool validation PASSED: {args.tool_path}", file=sys.stderr)
            sys.exit(0)
        else:
            if args.verbose:
                print(f"Tool validation FAILED: {args.tool_path}", file=sys.stderr)
                if "error" in result:
                    print(f"Error: {result['error']}", file=sys.stderr)
            sys.exit(1)
    
    except Exception as e:
        print(f"ERROR: Security validation failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
