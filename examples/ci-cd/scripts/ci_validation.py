#!/usr/bin/env python3
"""
CI Validation Suite for Buck2 Protobuf Projects

This module provides comprehensive validation functions for use in CI/CD pipelines,
integrating with Buck2 build system and governance frameworks.
"""

import os
import sys
import json
import glob
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import argparse
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CIValidationSuite:
    """Comprehensive CI validation suite for protobuf projects."""
    
    def __init__(self, 
                 project_root: str = ".",
                 verbose: bool = True,
                 buck2_binary: str = "buck2"):
        """Initialize validation suite.
        
        Args:
            project_root: Root directory of the project
            verbose: Enable verbose logging
            buck2_binary: Path to Buck2 binary
        """
        self.project_root = Path(project_root).resolve()
        self.verbose = verbose
        self.buck2_binary = buck2_binary
        self.validation_results = {}
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"Initialized CI validation suite for {self.project_root}")
    
    def run_command(self, cmd: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """Run shell command and return results.
        
        Args:
            cmd: Command and arguments as list
            cwd: Working directory (defaults to project root)
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if cwd is None:
            cwd = str(self.project_root)
        
        logger.debug(f"Running command: {' '.join(cmd)} in {cwd}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return 124, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return 1, "", str(e)
    
    def validate_project_structure(self) -> bool:
        """Validate basic project structure."""
        logger.info("🔍 Validating project structure...")
        
        required_files = [".buckconfig"]
        optional_files = ["governance.yaml", "registry.yaml"]
        
        errors = []
        
        # Check required files
        for file in required_files:
            file_path = self.project_root / file
            if not file_path.exists():
                errors.append(f"Missing required file: {file}")
            else:
                logger.debug(f"✅ Found required file: {file}")
        
        # Check for proto files
        proto_files = list(self.project_root.glob("**/*.proto"))
        if not proto_files:
            errors.append("No .proto files found in project")
        else:
            logger.info(f"Found {len(proto_files)} protobuf files")
        
        # Check for BUCK files
        buck_files = list(self.project_root.glob("**/BUCK"))
        if not buck_files:
            logger.warning("No BUCK files found - this may be expected for some projects")
        else:
            logger.info(f"Found {len(buck_files)} BUCK files")
        
        # Store results
        self.validation_results['project_structure'] = {
            'passed': len(errors) == 0,
            'errors': errors,
            'proto_files': len(proto_files),
            'buck_files': len(buck_files)
        }
        
        if errors:
            for error in errors:
                logger.error(f"❌ {error}")
            return False
        
        logger.info("✅ Project structure validation passed")
        return True
    
    def validate_buck2_setup(self) -> bool:
        """Validate Buck2 installation and configuration."""
        logger.info("🔧 Validating Buck2 setup...")
        
        # Check Buck2 binary
        returncode, stdout, stderr = self.run_command([self.buck2_binary, "--version"])
        if returncode != 0:
            logger.error(f"❌ Buck2 not available: {stderr}")
            self.validation_results['buck2_setup'] = {
                'passed': False,
                'error': f"Buck2 binary not found or not working: {stderr}"
            }
            return False
        
        buck2_version = stdout.strip()
        logger.info(f"Buck2 version: {buck2_version}")
        
        # Check .buckconfig
        buckconfig_path = self.project_root / ".buckconfig"
        if not buckconfig_path.exists():
            logger.error("❌ .buckconfig file not found")
            self.validation_results['buck2_setup'] = {
                'passed': False,
                'error': ".buckconfig file not found"
            }
            return False
        
        # Test Buck2 query
        returncode, stdout, stderr = self.run_command([self.buck2_binary, "query", "//:*"])
        if returncode != 0:
            logger.warning(f"Buck2 query test failed: {stderr}")
        
        self.validation_results['buck2_setup'] = {
            'passed': True,
            'version': buck2_version,
            'query_working': returncode == 0
        }
        
        logger.info("✅ Buck2 setup validation passed")
        return True
    
    def validate_protobuf_schemas(self) -> bool:
        """Validate all protobuf schemas."""
        logger.info("📋 Validating protobuf schemas...")
        
        proto_files = list(self.project_root.glob("**/*.proto"))
        if not proto_files:
            logger.warning("No protobuf files found to validate")
            self.validation_results['protobuf_schemas'] = {
                'passed': True,
                'files_validated': 0,
                'errors': []
            }
            return True
        
        errors = []
        validated_count = 0
        
        for proto_file in proto_files:
            # Skip files in buck-out or similar directories
            if 'buck-out' in str(proto_file) or '.git' in str(proto_file):
                continue
            
            logger.debug(f"Validating: {proto_file}")
            
            # Use protoc to validate syntax
            returncode, stdout, stderr = self.run_command([
                "protoc",
                f"--proto_path={self.project_root}",
                "--descriptor_set_out=/dev/null",
                str(proto_file.relative_to(self.project_root))
            ])
            
            if returncode != 0:
                error_msg = f"Validation failed for {proto_file}: {stderr}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
            else:
                validated_count += 1
                logger.debug(f"✅ {proto_file} validated successfully")
        
        self.validation_results['protobuf_schemas'] = {
            'passed': len(errors) == 0,
            'files_validated': validated_count,
            'total_files': len(proto_files),
            'errors': errors
        }
        
        if errors:
            logger.error(f"❌ {len(errors)} protobuf validation errors")
            return False
        
        logger.info(f"✅ {validated_count} protobuf files validated successfully")
        return True
    
    def validate_buck2_targets(self) -> bool:
        """Validate Buck2 target definitions."""
        logger.info("🎯 Validating Buck2 targets...")
        
        # Query all proto_library targets
        returncode, stdout, stderr = self.run_command([
            self.buck2_binary, "query", "kind(proto_library, //...)"
        ])
        
        if returncode != 0:
            if "No targets found" in stderr or "No matching targets" in stderr:
                logger.info("No proto_library targets found - this may be expected")
                self.validation_results['buck2_targets'] = {
                    'passed': True,
                    'proto_targets': 0,
                    'build_successful': True
                }
                return True
            else:
                logger.error(f"❌ Buck2 query failed: {stderr}")
                self.validation_results['buck2_targets'] = {
                    'passed': False,
                    'error': f"Buck2 query failed: {stderr}"
                }
                return False
        
        targets = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
        logger.info(f"Found {len(targets)} proto_library targets")
        
        if not targets:
            logger.info("No proto_library targets to build")
            self.validation_results['buck2_targets'] = {
                'passed': True,
                'proto_targets': 0,
                'build_successful': True
            }
            return True
        
        # Try to build all proto targets
        logger.info("Building all proto_library targets...")
        returncode, stdout, stderr = self.run_command([
            self.buck2_binary, "build"
        ] + targets)
        
        build_successful = returncode == 0
        
        if not build_successful:
            logger.error(f"❌ Buck2 build failed: {stderr}")
        else:
            logger.info("✅ All proto_library targets built successfully")
        
        self.validation_results['buck2_targets'] = {
            'passed': build_successful,
            'proto_targets': len(targets),
            'build_successful': build_successful,
            'targets': targets[:10],  # Store first 10 for reference
            'build_output': stderr if not build_successful else None
        }
        
        return build_successful
    
    def validate_governance_compliance(self) -> bool:
        """Validate governance compliance if configured."""
        logger.info("🔒 Checking governance compliance...")
        
        governance_file = self.project_root / "governance.yaml"
        if not governance_file.exists():
            logger.info("No governance.yaml found - skipping governance validation")
            self.validation_results['governance_compliance'] = {
                'passed': True,
                'configured': False,
                'message': "No governance configuration found"
            }
            return True
        
        # Check for governance targets
        returncode, stdout, stderr = self.run_command([
            self.buck2_binary, "query", "kind(schema_review, //...)"
        ])
        
        governance_targets = []
        if returncode == 0 and stdout.strip():
            governance_targets = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
        
        # Check for breaking change targets
        returncode, stdout, stderr = self.run_command([
            self.buck2_binary, "query", "kind(bsr_breaking_check, //...)"
        ])
        
        breaking_change_targets = []
        if returncode == 0 and stdout.strip():
            breaking_change_targets = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
        
        self.validation_results['governance_compliance'] = {
            'passed': True,
            'configured': True,
            'governance_targets': len(governance_targets),
            'breaking_change_targets': len(breaking_change_targets)
        }
        
        logger.info(f"✅ Governance validation completed")
        logger.info(f"   - Schema review targets: {len(governance_targets)}")
        logger.info(f"   - Breaking change targets: {len(breaking_change_targets)}")
        
        return True
    
    def run_security_checks(self) -> bool:
        """Run security validation checks."""
        logger.info("🔒 Running security checks...")
        
        security_issues = []
        proto_files = list(self.project_root.glob("**/*.proto"))
        
        for proto_file in proto_files:
            # Skip generated/temporary files
            if 'buck-out' in str(proto_file) or '.git' in str(proto_file):
                continue
            
            try:
                with open(proto_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    line_lower = line.lower()
                    
                    # Check for potential secrets
                    suspicious_keywords = ['password', 'secret', 'token', 'key', 'credential']
                    for keyword in suspicious_keywords:
                        if keyword in line_lower and any(marker in line for marker in ['=', ':', 'default']):
                            security_issues.append({
                                'file': str(proto_file.relative_to(self.project_root)),
                                'line': i,
                                'issue': 'potential_secret',
                                'description': f"Potential hardcoded {keyword}",
                                'severity': 'warning'
                            })
                    
                    # Check for overly permissive types
                    if 'google.protobuf.Any' in line:
                        security_issues.append({
                            'file': str(proto_file.relative_to(self.project_root)),
                            'line': i,
                            'issue': 'permissive_type',
                            'description': "Use of google.protobuf.Any may pose security risks",
                            'severity': 'info'
                        })
            
            except Exception as e:
                logger.warning(f"Could not read {proto_file}: {e}")
        
        # Report security issues
        high_severity_count = len([i for i in security_issues if i['severity'] == 'error'])
        
        self.validation_results['security_checks'] = {
            'passed': high_severity_count == 0,
            'issues': security_issues,
            'high_severity_count': high_severity_count
        }
        
        if security_issues:
            logger.warning(f"⚠️  Found {len(security_issues)} security considerations:")
            for issue in security_issues:
                level = "❌" if issue['severity'] == 'error' else "⚠️"
                logger.warning(f"  {level} {issue['file']}:{issue['line']} - {issue['description']}")
        else:
            logger.info("✅ No security issues detected")
        
        return high_severity_count == 0
    
    def generate_validation_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report."""
        logger.info("📊 Generating validation report...")
        
        # Calculate overall status
        all_passed = all(
            result.get('passed', False) 
            for result in self.validation_results.values()
        )
        
        report = {
            'timestamp': str(Path.cwd()),  # We'll use a simple marker
            'overall_status': 'PASSED' if all_passed else 'FAILED',
            'project_root': str(self.project_root),
            'validation_results': self.validation_results,
            'summary': {
                'total_checks': len(self.validation_results),
                'passed_checks': sum(1 for r in self.validation_results.values() if r.get('passed', False)),
                'failed_checks': sum(1 for r in self.validation_results.values() if not r.get('passed', True))
            }
        }
        
        return report
    
    def run_all_validations(self) -> bool:
        """Run all validation checks."""
        logger.info("🚀 Starting comprehensive CI validation...")
        
        checks = [
            ('project_structure', self.validate_project_structure),
            ('buck2_setup', self.validate_buck2_setup),
            ('protobuf_schemas', self.validate_protobuf_schemas),
            ('buck2_targets', self.validate_buck2_targets),
            ('governance_compliance', self.validate_governance_compliance),
            ('security_checks', self.run_security_checks)
        ]
        
        overall_success = True
        
        for check_name, check_func in checks:
            try:
                logger.info(f"\n--- Running {check_name} validation ---")
                success = check_func()
                if not success:
                    overall_success = False
                    logger.error(f"❌ {check_name} validation failed")
                else:
                    logger.info(f"✅ {check_name} validation passed")
            except Exception as e:
                logger.error(f"❌ {check_name} validation crashed: {e}")
                self.validation_results[check_name] = {
                    'passed': False,
                    'error': f"Validation crashed: {e}"
                }
                overall_success = False
        
        # Generate final report
        report = self.generate_validation_report()
        
        logger.info(f"\n{'='*50}")
        logger.info(f"🎯 CI VALIDATION SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"Overall Status: {report['overall_status']}")
        logger.info(f"Checks Passed: {report['summary']['passed_checks']}/{report['summary']['total_checks']}")
        
        if overall_success:
            logger.info("🎉 All validations passed! Ready for CI/CD pipeline.")
        else:
            logger.error("💥 Some validations failed. Please review and fix issues.")
        
        return overall_success


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CI Validation Suite for Buck2 Protobuf Projects"
    )
    parser.add_argument(
        "--project-root", 
        default=".",
        help="Root directory of the project (default: current directory)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--buck2-binary",
        default="buck2",
        help="Path to Buck2 binary (default: buck2)"
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output-file",
        help="Output file for validation report (default: stdout)"
    )
    
    args = parser.parse_args()
    
    # Initialize validation suite
    validator = CIValidationSuite(
        project_root=args.project_root,
        verbose=args.verbose,
        buck2_binary=args.buck2_binary
    )
    
    # Run validations
    success = validator.run_all_validations()
    
    # Output report
    if args.output_format == "json":
        report = validator.generate_validation_report()
        output = json.dumps(report, indent=2)
    else:
        output = f"CI Validation {'PASSED' if success else 'FAILED'}"
    
    if args.output_file:
        with open(args.output_file, 'w') as f:
            f.write(output)
        logger.info(f"Report written to {args.output_file}")
    else:
        print(output)
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
