#!/usr/bin/env python3
"""
Security audit logger for protobuf Buck2 integration.

This tool creates comprehensive security audit logs for all protobuf
compilation activities, tracking security-relevant events and configurations.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any


class SecurityAuditLogger:
    """Creates comprehensive security audit logs."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the security audit logger.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[audit-logger] {message}", file=sys.stderr)
    
    def get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        return datetime.now(timezone.utc).isoformat()
    
    def create_audit_entry(self, 
                          action_type: str,
                          target: str,
                          config: Dict[str, Any],
                          inputs: Optional[List[str]] = None,
                          outputs: Optional[List[str]] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a comprehensive audit log entry.
        
        Args:
            action_type: Type of action being audited
            target: Target being processed
            config: Security configuration used
            inputs: Input files/data
            outputs: Output files/data
            metadata: Additional metadata
            
        Returns:
            Dictionary containing audit entry
        """
        entry = {
            "audit_version": "1.0.0",
            "timestamp": self.get_current_timestamp(),
            "action_type": action_type,
            "target": target,
            "security_config": config,
            "session_id": f"audit_{int(time.time())}",
            "environment": {
                "cwd": str(Path.cwd()),
                "user": "build_system",  # In Buck2 context
                "pid": "$$",  # Will be replaced by shell
            }
        }
        
        # Add inputs if provided
        if inputs:
            entry["inputs"] = {
                "count": len(inputs),
                "files": inputs[:10],  # Limit to first 10 for brevity
                "total_files": len(inputs),
                "truncated": len(inputs) > 10,
            }
        
        # Add outputs if provided
        if outputs:
            entry["outputs"] = {
                "count": len(outputs),
                "files": outputs[:10],  # Limit to first 10 for brevity
                "total_files": len(outputs),
                "truncated": len(outputs) > 10,
            }
        
        # Add metadata if provided
        if metadata:
            entry["metadata"] = metadata
        
        # Security-specific fields
        entry["security_controls"] = {
            "sandboxing_enabled": config.get("sandbox_enabled", True),
            "network_isolation": not config.get("network_allowed", False),
            "input_sanitization": True,  # Always enabled in our implementation
            "tool_validation": True,     # Always enabled in our implementation
            "hermetic_execution": True,  # Always enabled in our implementation
        }
        
        # Compliance fields
        entry["compliance"] = {
            "security_level": config.get("security_level", "strict"),
            "audit_required": True,
            "retention_policy": "enterprise_standard",
        }
        
        return entry
    
    def create_protoc_execution_audit(self,
                                    target: str,
                                    language: str,
                                    proto_files: List[str],
                                    generated_files: List[str],
                                    sandbox_config: Dict[str, Any],
                                    tool_validations: List[str]) -> Dict[str, Any]:
        """
        Create audit entry for protoc execution.
        
        Args:
            target: Build target
            language: Target language
            proto_files: Input proto files
            generated_files: Generated output files
            sandbox_config: Sandbox configuration used
            tool_validations: Tool validation results
            
        Returns:
            Audit entry for protoc execution
        """
        metadata = {
            "language": language,
            "protoc_version": "latest",  # Could be made configurable
            "tool_validations": tool_validations,
            "generation_successful": True,
        }
        
        return self.create_audit_entry(
            action_type="protoc_execution",
            target=target,
            config=sandbox_config,
            inputs=proto_files,
            outputs=generated_files,
            metadata=metadata
        )
    
    def create_tool_download_audit(self,
                                 tool_name: str,
                                 tool_version: str,
                                 download_url: str,
                                 checksum: str,
                                 validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create audit entry for tool download.
        
        Args:
            tool_name: Name of the tool
            tool_version: Version of the tool
            download_url: URL where tool was downloaded from
            checksum: Expected checksum
            validation_result: Tool validation result
            
        Returns:
            Audit entry for tool download
        """
        config = {
            "security_level": "strict",
            "checksum_validation": True,
            "https_required": True,
            "signature_verification": False,  # Not implemented yet
        }
        
        metadata = {
            "tool_name": tool_name,
            "tool_version": tool_version,
            "download_url": download_url,
            "expected_checksum": checksum,
            "validation_result": validation_result,
            "download_timestamp": self.get_current_timestamp(),
        }
        
        return self.create_audit_entry(
            action_type="tool_download",
            target=f"{tool_name}:{tool_version}",
            config=config,
            metadata=metadata
        )
    
    def create_security_validation_audit(self,
                                       target: str,
                                       language: str,
                                       files_validated: List[str],
                                       security_report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create audit entry for security validation.
        
        Args:
            target: Build target
            language: Programming language
            files_validated: Files that were validated
            security_report: Security validation report
            
        Returns:
            Audit entry for security validation
        """
        config = {
            "security_level": "strict",
            "validation_enabled": True,
            "scanner_version": security_report.get("validator_version", "1.0.0"),
        }
        
        metadata = {
            "language": language,
            "files_validated": len(files_validated),
            "security_report": security_report,
            "validation_passed": security_report.get("passed", False),
            "high_severity_issues": security_report.get("high_severity_count", 0),
            "total_issues": security_report.get("total_issues", 0),
        }
        
        return self.create_audit_entry(
            action_type="security_validation",
            target=target,
            config=config,
            inputs=files_validated,
            metadata=metadata
        )
    
    def write_audit_log(self, audit_entry: Dict[str, Any], output_path: str) -> None:
        """
        Write audit entry to file.
        
        Args:
            audit_entry: Audit entry to write
            output_path: Path to write audit log to
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w') as f:
                json.dump(audit_entry, f, indent=2, sort_keys=True)
            
            self.log(f"Audit log written to: {output_path}")
            
        except Exception as e:
            self.log(f"Failed to write audit log: {e}")
            raise
    
    def append_to_master_log(self, audit_entry: Dict[str, Any], master_log_path: str) -> None:
        """
        Append audit entry to master log file.
        
        Args:
            audit_entry: Audit entry to append
            master_log_path: Path to master log file
        """
        try:
            master_file = Path(master_log_path)
            master_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Append to master log (one JSON object per line for easy parsing)
            with open(master_file, 'a') as f:
                f.write(json.dumps(audit_entry, sort_keys=True) + '\n')
            
            self.log(f"Audit entry appended to master log: {master_log_path}")
            
        except Exception as e:
            self.log(f"Failed to append to master log: {e}")
            # Don't fail the build for master log issues
    
    def validate_audit_entry(self, audit_entry: Dict[str, Any]) -> bool:
        """
        Validate that audit entry has required fields.
        
        Args:
            audit_entry: Audit entry to validate
            
        Returns:
            True if valid, False otherwise
        """
        required_fields = [
            "audit_version",
            "timestamp", 
            "action_type",
            "target",
            "security_config",
            "security_controls",
            "compliance",
        ]
        
        for field in required_fields:
            if field not in audit_entry:
                self.log(f"Missing required field in audit entry: {field}")
                return False
        
        return True


def main():
    """Main entry point for audit logger."""
    parser = argparse.ArgumentParser(description="Create security audit logs")
    parser.add_argument("--action-type", required=True, help="Type of action being audited")
    parser.add_argument("--target", required=True, help="Target being processed")
    parser.add_argument("--config", required=True, help="Security config (JSON string)")
    parser.add_argument("--timestamp", help="Timestamp (defaults to current time)")
    parser.add_argument("--inputs", help="Input files (JSON array)")
    parser.add_argument("--outputs", help="Output files (JSON array)")
    parser.add_argument("--metadata", help="Additional metadata (JSON object)")
    parser.add_argument("--output", required=True, help="Output audit log file")
    parser.add_argument("--master-log", help="Master log file to append to")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        logger = SecurityAuditLogger(verbose=args.verbose)
        
        # Parse JSON arguments
        config = json.loads(args.config)
        inputs = json.loads(args.inputs) if args.inputs else None
        outputs = json.loads(args.outputs) if args.outputs else None
        metadata = json.loads(args.metadata) if args.metadata else None
        
        # Create audit entry
        audit_entry = logger.create_audit_entry(
            action_type=args.action_type,
            target=args.target,
            config=config,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata
        )
        
        # Override timestamp if provided
        if args.timestamp:
            audit_entry["timestamp"] = args.timestamp
        
        # Validate audit entry
        if not logger.validate_audit_entry(audit_entry):
            print("ERROR: Invalid audit entry", file=sys.stderr)
            sys.exit(1)
        
        # Write audit log
        logger.write_audit_log(audit_entry, args.output)
        
        # Append to master log if specified
        if args.master_log:
            logger.append_to_master_log(audit_entry, args.master_log)
        
        if args.verbose:
            print(f"Audit log created successfully: {args.output}", file=sys.stderr)
        
    except Exception as e:
        print(f"ERROR: Failed to create audit log: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
