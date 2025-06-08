#!/usr/bin/env python3
"""
Comprehensive ORAS Test Runner

This script provides a unified interface for running all ORAS integration tests
with various options and configurations.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from test.oras.utils.test_helpers import (
    validate_oras_environment, 
    CoverageMeasurement,
    TestReporter
)


class OrasTestRunner:
    """Comprehensive test runner for ORAS integration tests."""
    
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.test_dir = Path(__file__).parent
        self.project_root = self.test_dir.parent.parent
        self.results = []
        self.start_time = time.time()
        
        # Initialize reporter
        self.reporter = TestReporter(self.test_dir / "reports")
        
        # Initialize coverage measurement
        self.coverage = CoverageMeasurement(target_coverage=95.0)
    
    def validate_environment(self) -> bool:
        """Validate test environment before running tests."""
        print("🔍 Validating ORAS test environment...")
        
        try:
            env_check = validate_oras_environment()
            
            if env_check["overall"]["valid"]:
                print("✅ Environment validation passed")
                self._print_environment_details(env_check)
                return True
            else:
                print("❌ Environment validation failed")
                self._print_environment_issues(env_check)
                return False
                
        except Exception as e:
            print(f"❌ Environment validation error: {e}")
            return False
    
    def _print_environment_details(self, env_check: Dict[str, Any]):
        """Print environment validation details."""
        print(f"  Python: {env_check['python_version']['actual']}")
        print(f"  Network: {'✅' if env_check['network_connectivity']['available'] else '❌'}")
        print(f"  Disk: {env_check['disk_space']['available_gb']:.1f}GB free")
    
    def _print_environment_issues(self, env_check: Dict[str, Any]):
        """Print environment validation issues."""
        for category, details in env_check.items():
            if category == "overall":
                continue
            
            if isinstance(details, dict):
                if not details.get("valid", details.get("available", True)):
                    print(f"  ❌ {category}: {details}")
    
    def run_test_category(self, category: str) -> Dict[str, Any]:
        """Run a specific test category."""
        print(f"\n🧪 Running {category} tests...")
        start_time = time.time()
        
        # Build pytest command
        cmd = self._build_pytest_command(category)
        
        try:
            # Run tests
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=self.args.timeout
            )
            
            duration = time.time() - start_time
            success = result.returncode == 0
            
            # Parse test results
            test_result = {
                "category": category,
                "success": success,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
            self.results.append(test_result)
            self.reporter.add_result(
                f"{category}_tests",
                "passed" if success else "failed",
                duration,
                {"stdout_lines": len(result.stdout.splitlines())}
            )
            
            # Print result
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"  {status} ({duration:.1f}s)")
            
            if not success and self.args.verbose:
                print(f"  Error output: {result.stderr}")
            
            return test_result
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"  ⏱️ TIMEOUT ({duration:.1f}s)")
            
            test_result = {
                "category": category,
                "success": False,
                "duration": duration,
                "error": "timeout",
                "timeout": True
            }
            
            self.results.append(test_result)
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            print(f"  ❌ ERROR: {e}")
            
            test_result = {
                "category": category,
                "success": False,
                "duration": duration,
                "error": str(e)
            }
            
            self.results.append(test_result)
            return test_result
    
    def _build_pytest_command(self, category: str) -> List[str]:
        """Build pytest command for specific category."""
        cmd = ["python", "-m", "pytest", "test/oras/"]
        
        # Add coverage if requested
        if self.args.coverage:
            cmd.extend([
                "--cov=tools",
                "--cov-report=term-missing",
                "--cov-report=html"
            ])
        
        # Add verbosity
        if self.args.verbose:
            cmd.append("-v")
        else:
            cmd.append("-q")
        
        # Add category-specific options
        if category == "unit":
            cmd.extend(["-m", "not real_registry and not slow and not benchmark"])
        elif category == "integration":
            cmd.extend(["test/oras/test_integration.py"])
            if not self.args.real_registry:
                cmd.extend(["-m", "not real_registry"])
        elif category == "performance":
            cmd.extend([
                "test/oras/test_performance.py",
                "-m", "benchmark"
            ])
        elif category == "security":
            cmd.extend([
                "test/oras/test_security.py",
                "-m", "security"
            ])
        elif category == "failure":
            cmd.extend([
                "test/oras/test_failure_scenarios.py",
                "-m", "failure_scenario"
            ])
        
        # Add platform filter
        if self.args.platform:
            cmd.extend(["--platform", self.args.platform])
        
        # Add real registry flag
        if self.args.real_registry:
            cmd.append("--real-registry")
        
        # Add timeout
        cmd.extend(["--timeout", str(self.args.timeout)])
        
        # Add maxfail
        cmd.extend(["--maxfail", "5"])
        
        return cmd
    
    def run_coverage_analysis(self) -> Dict[str, Any]:
        """Run comprehensive coverage analysis."""
        if not self.args.coverage:
            return {"skipped": True}
        
        print("\n📊 Running coverage analysis...")
        
        coverage_cmd = [
            "python", "-m", "pytest", "test/oras/",
            "--cov=tools",
            "--cov-report=json",
            "--cov-report=html",
            "--cov-report=term-missing",
            "-m", "not real_registry and not slow"
        ]
        
        result = subprocess.run(
            coverage_cmd,
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        
        # Load coverage data
        coverage_file = self.project_root / "coverage.json"
        if coverage_file.exists():
            with open(coverage_file) as f:
                coverage_data = json.load(f)
            
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
            
            if total_coverage >= 95.0:
                print(f"  ✅ Coverage: {total_coverage:.1f}% (target: 95%)")
            else:
                print(f"  ❌ Coverage: {total_coverage:.1f}% (target: 95%)")
            
            return {
                "success": total_coverage >= 95.0,
                "coverage": total_coverage,
                "target": 95.0,
                "details": coverage_data
            }
        else:
            print("  ❌ Coverage data not available")
            return {"success": False, "error": "No coverage data"}
    
    def generate_report(self) -> Path:
        """Generate comprehensive test report."""
        print("\n📋 Generating test report...")
        
        # Generate both JSON and HTML reports
        json_report = self.reporter.generate_report("json")
        html_report = self.reporter.generate_report("html")
        
        print(f"  📄 JSON report: {json_report}")
        print(f"  🌐 HTML report: {html_report}")
        
        return html_report
    
    def print_summary(self):
        """Print test execution summary."""
        total_duration = time.time() - self.start_time
        
        print("\n" + "="*60)
        print("🎯 ORAS Integration Test Summary")
        print("="*60)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total test categories: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success rate: {passed_tests/total_tests*100:.1f}%" if total_tests > 0 else "N/A")
        print(f"Total duration: {total_duration:.1f}s")
        
        # Show category breakdown
        print("\nCategory Results:")
        for result in self.results:
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            duration = result["duration"]
            category = result["category"]
            print(f"  {category:<15} {status:<8} ({duration:.1f}s)")
        
        # Show next steps
        if failed_tests > 0:
            print("\n⚠️ Next Steps:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - Fix {result['category']} test failures")
                    if result.get("error"):
                        print(f"    Error: {result['error']}")
        else:
            print("\n🎉 All tests passed! ORAS integration is working correctly.")
    
    def run_all(self) -> bool:
        """Run all tests based on configuration."""
        print("🚀 Starting ORAS Comprehensive Test Suite")
        print("="*60)
        
        # Validate environment
        if not self.validate_environment():
            return False
        
        # Determine test categories to run
        if self.args.category == "all":
            categories = ["unit", "integration", "performance", "security", "failure"]
        else:
            categories = [self.args.category]
        
        # Run tests
        success = True
        for category in categories:
            result = self.run_test_category(category)
            if not result["success"]:
                success = False
                
                # Stop on first failure if fail_fast is enabled
                if self.args.fail_fast:
                    print(f"\n⏹️ Stopping execution due to {category} test failure")
                    break
        
        # Run coverage analysis
        if self.args.coverage:
            coverage_result = self.run_coverage_analysis()
            if not coverage_result.get("success", False):
                success = False
        
        # Generate reports
        if self.args.report:
            self.generate_report()
        
        # Print summary
        self.print_summary()
        
        return success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ORAS Integration Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --category unit                    # Run unit tests only
  %(prog)s --category integration --real-registry  # Run integration tests against real registry
  %(prog)s --coverage --report               # Run all tests with coverage and reports
  %(prog)s --category performance --timeout 1200    # Run performance tests with extended timeout
        """
    )
    
    parser.add_argument(
        "--category",
        choices=["all", "unit", "integration", "performance", "security", "failure"],
        default="all",
        help="Test category to run (default: all)"
    )
    
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage analysis"
    )
    
    parser.add_argument(
        "--real-registry",
        action="store_true",
        help="Test against real oras.birb.homes registry"
    )
    
    parser.add_argument(
        "--platform",
        help="Test specific platform (e.g., linux-x86_64)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Test timeout in seconds (default: 600)"
    )
    
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first test category failure"
    )
    
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate test reports"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )
    
    args = parser.parse_args()
    
    # Create and run test runner
    runner = OrasTestRunner(args)
    success = runner.run_all()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
