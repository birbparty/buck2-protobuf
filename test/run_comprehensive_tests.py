#!/usr/bin/env python3
"""
Master test runner for comprehensive protobuf Buck2 integration tests.

This script orchestrates the complete test suite including unit tests,
integration tests, performance benchmarks, and coverage measurement
to achieve >95% coverage and validate all performance targets.
"""

import os
import sys
import time
import argparse
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test.coverage.coverage_runner import CoverageRunner
from test.performance.benchmark_suite import PerformanceBenchmarks


class ComprehensiveTestRunner:
    """Master test runner for all test categories."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.results = {
            "timestamp": time.time(),
            "test_categories": {},
            "overall_summary": {},
            "quality_metrics": {}
        }
        self.start_time = time.time()
    
    def run_comprehensive_tests(self, test_categories: List[str]) -> Dict:
        """Run comprehensive test suite with specified categories."""
        print("🚀 Starting Comprehensive Test Suite")
        print("=" * 60)
        
        total_passed = 0
        total_failed = 0
        
        # Run each test category
        if "unit" in test_categories:
            result = self._run_unit_tests()
            self.results["test_categories"]["unit_tests"] = result
            total_passed += result.get("passed", 0)
            total_failed += result.get("failed", 0)
        
        if "integration" in test_categories:
            result = self._run_integration_tests()
            self.results["test_categories"]["integration_tests"] = result
            total_passed += result.get("passed", 0) 
            total_failed += result.get("failed", 0)
        
        if "performance" in test_categories:
            result = self._run_performance_tests()
            self.results["test_categories"]["performance_tests"] = result
            total_passed += result.get("passed", 0)
            total_failed += result.get("failed", 0)
        
        if "coverage" in test_categories:
            result = self._run_coverage_analysis()
            self.results["test_categories"]["coverage_analysis"] = result
        
        if "cross_language" in test_categories:
            result = self._run_cross_language_tests()
            self.results["test_categories"]["cross_language_tests"] = result
            total_passed += result.get("passed", 0)
            total_failed += result.get("failed", 0)
        
        # Generate comprehensive summary
        self._generate_comprehensive_summary(total_passed, total_failed)
        
        # Save comprehensive report
        self._save_comprehensive_report()
        
        return self.results
    
    def _run_unit_tests(self) -> Dict:
        """Run comprehensive unit test suite."""
        print("\n🧪 Running Unit Tests")
        print("-" * 40)
        
        test_commands = [
            (["python3", "-m", "pytest", "test/rules/proto_utils_test.py", "-v"], "Core Proto Utils"),
            (["python3", "test/rules/private_implementations_test.py"], "Private Implementations"),
            (["buck2", "test", "//test/rules:go_proto_test"], "Go Proto Rules"),
            (["buck2", "test", "//test/rules:python_proto_test"], "Python Proto Rules"),
            (["buck2", "test", "//test/rules:typescript_proto_test"], "TypeScript Proto Rules"),
            (["buck2", "test", "//test/rules:cpp_proto_test"], "C++ Proto Rules"),
            (["buck2", "test", "//test/rules:rust_proto_test"], "Rust Proto Rules"),
            (["buck2", "test", "//test:cache_test"], "Cache Implementation"),
            (["buck2", "test", "//test:security_test"], "Security Implementation"),
            (["buck2", "test", "//test:validation_test"], "Validation Implementation"),
        ]
        
        passed = 0
        failed = 0
        test_results = []
        
        for command, name in test_commands:
            print(f"  Running {name}...")
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    command,
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                duration = time.time() - start_time
                success = result.returncode == 0
                
                if success:
                    print(f"    ✓ {name} passed ({duration:.1f}s)")
                    passed += 1
                else:
                    print(f"    ✗ {name} failed ({duration:.1f}s)")
                    failed += 1
                
                test_results.append({
                    "name": name,
                    "success": success,
                    "duration_seconds": duration,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                
            except subprocess.TimeoutExpired:
                print(f"    ⏱ {name} timed out")
                failed += 1
                test_results.append({
                    "name": name,
                    "success": False,
                    "duration_seconds": 300,
                    "error": "Test timed out"
                })
            except Exception as e:
                print(f"    ❌ {name} error: {e}")
                failed += 1
                test_results.append({
                    "name": name,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "success_rate": passed / (passed + failed) if (passed + failed) > 0 else 0,
            "individual_results": test_results
        }
    
    def _run_integration_tests(self) -> Dict:
        """Run integration test suite."""
        print("\n🔧 Running Integration Tests")
        print("-" * 40)
        
        test_scripts = [
            ("test/integration/test_workflows.sh", "Core Workflows"),
            ("test/integration/test_go_compilation.sh", "Go Integration"),
            ("test/integration/test_python_compilation.sh", "Python Integration"),
            ("test/integration/test_typescript_compilation.sh", "TypeScript Integration"),
            ("test/integration/test_cpp_compilation.sh", "C++ Integration"),
            ("test/integration/test_rust_compilation.sh", "Rust Integration"),
            ("test/integration/test_multi_language.sh", "Multi-Language"),
            ("test/integration/test_validation.sh", "Validation"),
            ("test/integration/test_cache_performance.sh", "Cache Performance"),
        ]
        
        passed = 0
        failed = 0
        test_results = []
        
        for script_path, name in test_scripts:
            if not (self.project_root / script_path).exists():
                print(f"  ⚠ Skipping {name} - script not found")
                continue
                
            print(f"  Running {name}...")
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    ["bash", script_path],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout
                )
                
                duration = time.time() - start_time
                success = result.returncode == 0
                
                if success:
                    print(f"    ✓ {name} passed ({duration:.1f}s)")
                    passed += 1
                else:
                    print(f"    ✗ {name} failed ({duration:.1f}s)")
                    failed += 1
                
                test_results.append({
                    "name": name,
                    "success": success,
                    "duration_seconds": duration,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                
            except subprocess.TimeoutExpired:
                print(f"    ⏱ {name} timed out")
                failed += 1
                test_results.append({
                    "name": name,
                    "success": False,
                    "duration_seconds": 600,
                    "error": "Test timed out"
                })
            except Exception as e:
                print(f"    ❌ {name} error: {e}")
                failed += 1
                test_results.append({
                    "name": name,
                    "success": False,
                    "error": str(e)
                })
        
        return {
            "passed": passed,
            "failed": failed,
            "total": passed + failed,
            "success_rate": passed / (passed + failed) if (passed + failed) > 0 else 0,
            "individual_results": test_results
        }
    
    def _run_performance_tests(self) -> Dict:
        """Run performance benchmark suite."""
        print("\n⚡ Running Performance Tests")
        print("-" * 40)
        
        try:
            benchmarks = PerformanceBenchmarks(str(self.project_root))
            report = benchmarks.run_all_benchmarks()
            
            summary = report["summary"]
            targets_met = summary["targets_met"]
            targets_failed = summary["targets_failed"]
            
            print(f"  Performance Targets Met: {targets_met}/{targets_met + targets_failed}")
            print(f"  Max Memory Usage: {summary['max_memory_mb']:.1f}MB")
            print(f"  Regressions Detected: {summary['regressions_detected']}")
            
            return {
                "passed": targets_met,
                "failed": targets_failed,
                "total": targets_met + targets_failed,
                "success_rate": summary["success_rate"],
                "performance_report": report,
                "max_memory_mb": summary["max_memory_mb"],
                "regressions": summary["regressions_detected"]
            }
            
        except Exception as e:
            print(f"  ❌ Performance tests failed: {e}")
            return {
                "passed": 0,
                "failed": 1,
                "total": 1,
                "success_rate": 0,
                "error": str(e)
            }
    
    def _run_coverage_analysis(self) -> Dict:
        """Run coverage analysis."""
        print("\n📊 Running Coverage Analysis")
        print("-" * 40)
        
        try:
            coverage_runner = CoverageRunner(str(self.project_root))
            coverage_runner.setup_coverage_config()
            
            # Run unit tests with coverage
            unit_results = coverage_runner.run_unit_tests_with_coverage()
            
            # Run integration tests
            integration_results = coverage_runner.run_integration_tests()
            
            # Generate comprehensive report
            report = coverage_runner.generate_comprehensive_report()
            
            summary = report["summary"]
            coverage_pct = summary["coverage_percentage"]
            target_met = summary["coverage_target_met"]
            
            print(f"  Code Coverage: {coverage_pct:.1f}%")
            print(f"  Coverage Target (≥95%): {'✓' if target_met else '✗'}")
            print(f"  Quality Score: {summary['overall_quality_score']:.1%}")
            
            return {
                "coverage_percentage": coverage_pct,
                "target_met": target_met,
                "quality_score": summary["overall_quality_score"],
                "comprehensive_report": report,
                "unit_test_results": unit_results,
                "integration_test_results": integration_results
            }
            
        except Exception as e:
            print(f"  ❌ Coverage analysis failed: {e}")
            return {
                "coverage_percentage": 0,
                "target_met": False,
                "error": str(e)
            }
    
    def _run_cross_language_tests(self) -> Dict:
        """Run cross-language compatibility tests."""
        print("\n🌐 Running Cross-Language Tests")
        print("-" * 40)
        
        script_path = "test/integration/test_cross_language_compatibility.sh"
        if not (self.project_root / script_path).exists():
            print("  ⚠ Cross-language test script not found")
            return {"passed": 0, "failed": 1, "total": 1, "success_rate": 0}
        
        try:
            start_time = time.time()
            result = subprocess.run(
                ["bash", script_path],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=900  # 15 minute timeout
            )
            
            duration = time.time() - start_time
            success = result.returncode == 0
            
            if success:
                print(f"  ✓ Cross-language compatibility passed ({duration:.1f}s)")
                return {
                    "passed": 1,
                    "failed": 0,
                    "total": 1,
                    "success_rate": 1.0,
                    "duration_seconds": duration,
                    "stdout": result.stdout
                }
            else:
                print(f"  ✗ Cross-language compatibility failed ({duration:.1f}s)")
                return {
                    "passed": 0,
                    "failed": 1,
                    "total": 1,
                    "success_rate": 0.0,
                    "duration_seconds": duration,
                    "stderr": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            print("  ⏱ Cross-language tests timed out")
            return {
                "passed": 0,
                "failed": 1,
                "total": 1,
                "success_rate": 0.0,
                "error": "Test timed out"
            }
        except Exception as e:
            print(f"  ❌ Cross-language tests error: {e}")
            return {
                "passed": 0,
                "failed": 1,
                "total": 1,
                "success_rate": 0.0,
                "error": str(e)
            }
    
    def _generate_comprehensive_summary(self, total_passed: int, total_failed: int):
        """Generate comprehensive test summary."""
        duration = time.time() - self.start_time
        
        # Calculate overall metrics
        total_tests = total_passed + total_failed
        success_rate = total_passed / total_tests if total_tests > 0 else 0
        
        # Extract key quality metrics
        coverage_result = self.results["test_categories"].get("coverage_analysis", {})
        coverage_pct = coverage_result.get("coverage_percentage", 0)
        coverage_target_met = coverage_result.get("target_met", False)
        
        performance_result = self.results["test_categories"].get("performance_tests", {})
        performance_success_rate = performance_result.get("success_rate", 0)
        max_memory_mb = performance_result.get("max_memory_mb", 0)
        regressions = performance_result.get("regressions", 0)
        
        # Quality gates
        quality_gates = {
            "coverage_95_percent": coverage_pct >= 95,
            "performance_targets_met": performance_success_rate >= 0.95,
            "no_regressions": regressions == 0,
            "test_success_rate_90_percent": success_rate >= 0.90,
            "memory_under_1gb": max_memory_mb <= 1024
        }
        
        gates_passed = sum(quality_gates.values())
        total_gates = len(quality_gates)
        
        self.results["overall_summary"] = {
            "total_tests": total_tests,
            "tests_passed": total_passed,
            "tests_failed": total_failed,
            "success_rate": success_rate,
            "duration_seconds": duration,
            "coverage_percentage": coverage_pct,
            "coverage_target_met": coverage_target_met,
            "performance_success_rate": performance_success_rate,
            "max_memory_mb": max_memory_mb,
            "regressions_detected": regressions,
            "quality_gates": quality_gates,
            "quality_gates_passed": gates_passed,
            "quality_gates_total": total_gates,
            "overall_quality_score": gates_passed / total_gates
        }
        
        self.results["quality_metrics"] = {
            "meets_all_targets": gates_passed == total_gates,
            "production_ready": (
                coverage_pct >= 95 and
                performance_success_rate >= 0.95 and
                regressions == 0 and
                success_rate >= 0.90
            )
        }
    
    def _save_comprehensive_report(self):
        """Save comprehensive test report."""
        report_dir = self.project_root / "test" / "reports"
        report_dir.mkdir(exist_ok=True)
        
        # Save main report
        report_file = report_dir / f"comprehensive_test_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        # Save latest report (for CI)
        latest_file = report_dir / "latest_test_report.json"
        with open(latest_file, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📋 Test report saved to: {report_file}")
    
    def print_final_summary(self):
        """Print final comprehensive summary."""
        print("\n" + "=" * 60)
        print("🏁 COMPREHENSIVE TEST SUITE SUMMARY")
        print("=" * 60)
        
        summary = self.results["overall_summary"]
        quality = self.results["quality_metrics"]
        
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['tests_passed']}")
        print(f"Failed: {summary['tests_failed']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Duration: {summary['duration_seconds']:.1f}s")
        
        print(f"\n📊 Quality Metrics:")
        print(f"Coverage: {summary['coverage_percentage']:.1f}% (Target: ≥95%)")
        print(f"Performance: {summary['performance_success_rate']:.1%} targets met")
        print(f"Memory Usage: {summary['max_memory_mb']:.1f}MB")
        print(f"Regressions: {summary['regressions_detected']}")
        
        print(f"\n🎯 Quality Gates:")
        gates = summary['quality_gates']
        for gate_name, passed in gates.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {gate_name.replace('_', ' ').title()}")
        
        print(f"\nQuality Gates: {summary['quality_gates_passed']}/{summary['quality_gates_total']}")
        print(f"Overall Quality Score: {summary['overall_quality_score']:.1%}")
        
        if quality["production_ready"]:
            print(f"\n🎉 PRODUCTION READY - All quality targets met!")
            return True
        else:
            print(f"\n⚠️  NOT PRODUCTION READY - Quality targets not met")
            return False


def main():
    """Main entry point for comprehensive test runner."""
    parser = argparse.ArgumentParser(description="Run comprehensive protobuf Buck2 test suite")
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=["unit", "integration", "performance", "coverage", "cross_language", "all"],
        default=["all"],
        help="Test categories to run"
    )
    parser.add_argument(
        "--quick", 
        action="store_true",
        help="Run quick test suite (unit tests only)"
    )
    parser.add_argument(
        "--ci",
        action="store_true", 
        help="Run CI test suite (unit + integration + cross-language)"
    )
    
    args = parser.parse_args()
    
    # Determine test categories to run
    if args.quick:
        categories = ["unit"]
    elif args.ci:
        categories = ["unit", "integration", "cross_language"]
    elif "all" in args.categories:
        categories = ["unit", "integration", "performance", "coverage", "cross_language"]
    else:
        categories = args.categories
    
    # Fix project root calculation - go up one level from test directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    runner = ComprehensiveTestRunner(project_root)
    
    try:
        runner.run_comprehensive_tests(categories)
        production_ready = runner.print_final_summary()
        
        sys.exit(0 if production_ready else 1)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test suite failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
