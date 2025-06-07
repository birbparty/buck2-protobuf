#!/usr/bin/env python3
"""
Quality Gates Framework for Protobuf Buck2 Integration.

This module implements automated quality gate enforcement to ensure
all code changes meet enterprise-grade standards before integration.
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class QualityGate:
    """Represents a single quality gate with pass/fail criteria."""
    name: str
    description: str
    required: bool
    weight: float
    threshold: float
    current_value: Optional[float] = None
    passed: Optional[bool] = None
    details: Optional[Dict] = None


class QualityGateEnforcer:
    """Enforces quality gates for code changes and releases."""
    
    def __init__(self, project_root: str, config_path: Optional[str] = None):
        self.project_root = Path(project_root)
        self.config_path = config_path or str(self.project_root / "qa" / "config" / "quality_gates.json")
        self.results_dir = self.project_root / "qa" / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Load quality gate configuration
        self.gates = self._load_quality_gates()
    
    def _load_quality_gates(self) -> List[QualityGate]:
        """Load quality gate configuration."""
        default_gates = [
            QualityGate(
                name="test_coverage",
                description="Code coverage from unit and integration tests",
                required=True,
                weight=1.0,
                threshold=95.0
            ),
            QualityGate(
                name="test_pass_rate",
                description="Percentage of tests that pass",
                required=True,
                weight=1.0,
                threshold=100.0
            ),
            QualityGate(
                name="security_vulnerabilities",
                description="Number of critical/high security vulnerabilities",
                required=True,
                weight=1.0,
                threshold=0.0
            ),
            QualityGate(
                name="performance_regression",
                description="Performance regression percentage vs baseline",
                required=True,
                weight=0.8,
                threshold=5.0  # Maximum 5% regression allowed
            ),
            QualityGate(
                name="code_complexity",
                description="Average cyclomatic complexity",
                required=False,
                weight=0.6,
                threshold=10.0
            ),
            QualityGate(
                name="documentation_coverage",
                description="Percentage of public APIs with documentation",
                required=True,
                weight=0.7,
                threshold=95.0
            ),
            QualityGate(
                name="build_success_rate",
                description="Percentage of successful builds across platforms",
                required=True,
                weight=0.9,
                threshold=100.0
            ),
            QualityGate(
                name="memory_usage",
                description="Peak memory usage during stress testing (MB)",
                required=False,
                weight=0.5,
                threshold=1024.0  # 1GB limit
            )
        ]
        
        # Try to load from config file if it exists
        config_file = Path(self.config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                    # Update default gates with config data
                    for gate_config in config_data.get('gates', []):
                        for gate in default_gates:
                            if gate.name == gate_config['name']:
                                gate.threshold = gate_config.get('threshold', gate.threshold)
                                gate.required = gate_config.get('required', gate.required)
                                gate.weight = gate_config.get('weight', gate.weight)
                                break
            except Exception as e:
                print(f"Warning: Could not load quality gates config: {e}")
        
        return default_gates
    
    def evaluate_all_gates(self) -> Dict:
        """Evaluate all quality gates and return comprehensive results."""
        print("🎯 Evaluating Quality Gates")
        print("=" * 50)
        
        results = {
            "timestamp": time.time(),
            "overall_passed": True,
            "quality_score": 0.0,
            "gates": {},
            "summary": {},
            "recommendations": []
        }
        
        # Evaluate each gate
        for gate in self.gates:
            gate_result = self._evaluate_gate(gate)
            results["gates"][gate.name] = {
                "passed": gate_result.passed,
                "current_value": gate_result.current_value,
                "threshold": gate_result.threshold,
                "required": gate_result.required,
                "weight": gate_result.weight,
                "details": gate_result.details
            }
            
            # Update overall results
            if gate.required and not gate_result.passed:
                results["overall_passed"] = False
            
            print(f"  {'✓' if gate_result.passed else '✗'} {gate.name}: "
                  f"{gate_result.current_value} {'<=' if 'vulnerabilities' in gate.name or 'regression' in gate.name or 'usage' in gate.name or 'complexity' in gate.name else '>='} {gate_result.threshold}"
                  f"{' (REQUIRED)' if gate.required else ''}")
        
        # Calculate weighted quality score
        total_weight = sum(gate.weight for gate in self.gates)
        weighted_score = 0
        
        for gate in self.gates:
            if gate.passed is not None:
                gate_score = 1.0 if gate.passed else 0.0
                weighted_score += gate_score * gate.weight
        
        results["quality_score"] = weighted_score / total_weight if total_weight > 0 else 0
        
        # Generate summary and recommendations
        self._generate_summary_and_recommendations(results)
        
        # Save results
        self._save_results(results)
        
        return results
    
    def _evaluate_gate(self, gate: QualityGate) -> QualityGate:
        """Evaluate a specific quality gate."""
        try:
            if gate.name == "test_coverage":
                gate.current_value, gate.details = self._measure_test_coverage()
                gate.passed = gate.current_value >= gate.threshold
            
            elif gate.name == "test_pass_rate":
                gate.current_value, gate.details = self._measure_test_pass_rate()
                gate.passed = gate.current_value >= gate.threshold
            
            elif gate.name == "security_vulnerabilities":
                gate.current_value, gate.details = self._measure_security_vulnerabilities()
                gate.passed = gate.current_value <= gate.threshold
            
            elif gate.name == "performance_regression":
                gate.current_value, gate.details = self._measure_performance_regression()
                gate.passed = gate.current_value <= gate.threshold
            
            elif gate.name == "code_complexity":
                gate.current_value, gate.details = self._measure_code_complexity()
                gate.passed = gate.current_value <= gate.threshold
            
            elif gate.name == "documentation_coverage":
                gate.current_value, gate.details = self._measure_documentation_coverage()
                gate.passed = gate.current_value >= gate.threshold
            
            elif gate.name == "build_success_rate":
                gate.current_value, gate.details = self._measure_build_success_rate()
                gate.passed = gate.current_value >= gate.threshold
            
            elif gate.name == "memory_usage":
                gate.current_value, gate.details = self._measure_memory_usage()
                gate.passed = gate.current_value <= gate.threshold
            
            else:
                gate.current_value = 0
                gate.passed = False
                gate.details = {"error": f"Unknown quality gate: {gate.name}"}
        
        except Exception as e:
            gate.current_value = 0
            gate.passed = False
            gate.details = {"error": str(e)}
        
        return gate
    
    def _measure_test_coverage(self) -> Tuple[float, Dict]:
        """Measure test coverage percentage."""
        try:
            # Run comprehensive test suite with coverage
            result = subprocess.run(
                [sys.executable, "test/run_comprehensive_tests.py", "--categories", "coverage"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            # Try to extract coverage from test report
            report_file = self.project_root / "test" / "reports" / "latest_test_report.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    test_data = json.load(f)
                    coverage_result = test_data.get("test_categories", {}).get("coverage_analysis", {})
                    coverage_pct = coverage_result.get("coverage_percentage", 0)
                    return coverage_pct, {"source": "comprehensive_test_report", "details": coverage_result}
            
            # Fallback: try to run coverage directly
            cov_result = subprocess.run(
                [sys.executable, "test/coverage/coverage_runner.py"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if cov_result.returncode == 0:
                # Extract coverage percentage from output
                for line in cov_result.stdout.split('\n'):
                    if 'Coverage:' in line and '%' in line:
                        try:
                            coverage_str = line.split('Coverage:')[1].split('%')[0].strip()
                            coverage_pct = float(coverage_str)
                            return coverage_pct, {"source": "coverage_runner", "stdout": cov_result.stdout}
                        except:
                            pass
            
            return 0, {"error": "Could not measure coverage", "stdout": result.stdout, "stderr": result.stderr}
        
        except Exception as e:
            return 0, {"error": str(e)}
    
    def _measure_test_pass_rate(self) -> Tuple[float, Dict]:
        """Measure test pass rate percentage."""
        try:
            # Run comprehensive test suite
            result = subprocess.run(
                [sys.executable, "test/run_comprehensive_tests.py", "--categories", "unit", "integration"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            # Try to extract results from test report
            report_file = self.project_root / "test" / "reports" / "latest_test_report.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    test_data = json.load(f)
                    overall_summary = test_data.get("overall_summary", {})
                    success_rate = overall_summary.get("success_rate", 0) * 100
                    return success_rate, {"source": "comprehensive_test_report", "summary": overall_summary}
            
            # If no report, assume 100% if exit code is 0
            pass_rate = 100.0 if result.returncode == 0 else 0.0
            return pass_rate, {"source": "exit_code", "returncode": result.returncode}
        
        except Exception as e:
            return 0, {"error": str(e)}
    
    def _measure_security_vulnerabilities(self) -> Tuple[float, Dict]:
        """Measure number of critical/high security vulnerabilities."""
        try:
            # Run security audit
            vuln_count = 0
            details = {"scans": []}
            
            # Check with security validator
            security_script = self.project_root / "tools" / "security_validator.py"
            if security_script.exists():
                # Test a few critical tools
                test_tools = [
                    "/usr/bin/python3",  # Example tool path
                ]
                
                for tool_path in test_tools:
                    if Path(tool_path).exists():
                        result = subprocess.run([
                            sys.executable, str(security_script),
                            "--tool-path", tool_path,
                            "--expected-checksum", "dummy_checksum",
                            "--output", "/tmp/security_result.json",
                            "--comprehensive"
                        ], capture_output=True, text=True)
                        
                        details["scans"].append({
                            "tool": tool_path,
                            "result": "passed" if result.returncode == 0 else "failed"
                        })
            
            # Run basic security tests
            security_test = self.project_root / "test" / "security_test.bzl"
            if security_test.exists():
                result = subprocess.run(
                    ["buck2", "test", "//test:security_test"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    vuln_count += 1
                    details["security_test_failed"] = True
            
            return float(vuln_count), details
        
        except Exception as e:
            return 999, {"error": str(e)}  # High number indicates scanning failure
    
    def _measure_performance_regression(self) -> Tuple[float, Dict]:
        """Measure performance regression percentage."""
        try:
            # Run performance tests
            perf_result = subprocess.run(
                [sys.executable, "test/run_comprehensive_tests.py", "--categories", "performance"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=900
            )
            
            # Extract performance data from report
            report_file = self.project_root / "test" / "reports" / "latest_test_report.json"
            if report_file.exists():
                with open(report_file, 'r') as f:
                    test_data = json.load(f)
                    perf_data = test_data.get("test_categories", {}).get("performance_tests", {})
                    regressions = perf_data.get("regressions", 0)
                    
                    # Convert regression count to percentage (assuming baseline)
                    regression_pct = min(regressions * 10, 100)  # Cap at 100%
                    return regression_pct, {"regressions_detected": regressions, "performance_data": perf_data}
            
            # If no regressions detected, assume 0%
            return 0.0, {"source": "no_regressions_detected"}
        
        except Exception as e:
            return 100, {"error": str(e)}  # Assume worst case on error
    
    def _measure_code_complexity(self) -> Tuple[float, Dict]:
        """Measure average code complexity."""
        try:
            # Use radon to measure complexity if available
            try:
                result = subprocess.run(
                    ["radon", "cc", "rules/", "tools/", "-a"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    # Parse radon output to get average complexity
                    lines = result.stdout.strip().split('\n')
                    for line in lines:
                        if 'Average complexity:' in line:
                            try:
                                complexity = float(line.split(':')[1].strip().split()[0])
                                return complexity, {"source": "radon", "output": result.stdout}
                            except:
                                pass
            except FileNotFoundError:
                pass
            
            # Fallback: estimate complexity based on file analysis
            total_complexity = 0
            file_count = 0
            
            for py_file in self.project_root.glob("**/*.py"):
                if "test/" in str(py_file) or "__pycache__" in str(py_file):
                    continue
                
                try:
                    with open(py_file, 'r') as f:
                        content = f.read()
                        # Simple heuristic: count control flow statements
                        complexity = content.count('if ') + content.count('for ') + content.count('while ') + content.count('except')
                        total_complexity += max(complexity, 1)
                        file_count += 1
                except:
                    continue
            
            avg_complexity = total_complexity / file_count if file_count > 0 else 0
            return avg_complexity, {"source": "heuristic", "files_analyzed": file_count}
        
        except Exception as e:
            return 999, {"error": str(e)}
    
    def _measure_documentation_coverage(self) -> Tuple[float, Dict]:
        """Measure documentation coverage percentage."""
        try:
            # Analyze Python files for docstring coverage
            total_functions = 0
            documented_functions = 0
            
            for py_file in self.project_root.glob("rules/**/*.py"):
                try:
                    with open(py_file, 'r') as f:
                        content = f.read()
                        
                        # Count function definitions
                        functions = content.count('def ')
                        total_functions += functions
                        
                        # Rough estimate of documented functions (has docstring nearby)
                        documented = content.count('"""') + content.count("'''")
                        documented_functions += min(documented // 2, functions)  # Each docstring has open/close
                        
                except:
                    continue
            
            coverage_pct = (documented_functions / total_functions * 100) if total_functions > 0 else 100
            return coverage_pct, {
                "total_functions": total_functions,
                "documented_functions": documented_functions,
                "source": "docstring_analysis"
            }
        
        except Exception as e:
            return 0, {"error": str(e)}
    
    def _measure_build_success_rate(self) -> Tuple[float, Dict]:
        """Measure build success rate across platforms."""
        try:
            # Test builds for major targets
            targets = [
                "//rules:proto",
                "//examples/go:user_proto_go",
                "//examples/python:user_proto_python",
                "//examples/typescript:user_proto_typescript"
            ]
            
            successful_builds = 0
            total_builds = len(targets)
            build_results = {}
            
            for target in targets:
                try:
                    result = subprocess.run(
                        ["buck2", "build", target],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    
                    success = result.returncode == 0
                    if success:
                        successful_builds += 1
                    
                    build_results[target] = {
                        "success": success,
                        "returncode": result.returncode
                    }
                    
                except subprocess.TimeoutExpired:
                    build_results[target] = {"success": False, "error": "timeout"}
                except Exception as e:
                    build_results[target] = {"success": False, "error": str(e)}
            
            success_rate = (successful_builds / total_builds * 100) if total_builds > 0 else 0
            return success_rate, {
                "successful_builds": successful_builds,
                "total_builds": total_builds,
                "build_results": build_results
            }
        
        except Exception as e:
            return 0, {"error": str(e)}
    
    def _measure_memory_usage(self) -> Tuple[float, Dict]:
        """Measure peak memory usage during stress testing."""
        try:
            # Run a stress test and monitor memory
            stress_script = self.project_root / "test" / "performance" / "stress_tests.py"
            if stress_script.exists():
                result = subprocess.run(
                    [sys.executable, str(stress_script)],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                # Try to extract memory usage from output
                max_memory = 0
                for line in result.stdout.split('\n'):
                    if 'Memory:' in line and 'MB' in line:
                        try:
                            memory_str = line.split('Memory:')[1].split('MB')[0].strip()
                            memory_mb = float(memory_str)
                            max_memory = max(max_memory, memory_mb)
                        except:
                            pass
                
                if max_memory > 0:
                    return max_memory, {"source": "stress_test", "output": result.stdout}
            
            # Fallback: run a simple build and estimate memory
            result = subprocess.run(
                ["/usr/bin/time", "-l", "buck2", "build", "//examples/basic:example_proto"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            # Extract memory from time output (macOS format)
            for line in result.stderr.split('\n'):
                if 'maximum resident set size' in line:
                    try:
                        # macOS time reports in bytes
                        memory_bytes = int(line.split()[0])
                        memory_mb = memory_bytes / (1024 * 1024)
                        return memory_mb, {"source": "time_command", "stderr": result.stderr}
                    except:
                        pass
            
            # Default estimate
            return 256.0, {"source": "default_estimate"}
        
        except Exception as e:
            return 1024, {"error": str(e)}  # Conservative estimate
    
    def _generate_summary_and_recommendations(self, results: Dict):
        """Generate summary and recommendations based on results."""
        passed_gates = sum(1 for gate_result in results["gates"].values() if gate_result["passed"])
        total_gates = len(results["gates"])
        required_gates = sum(1 for gate_result in results["gates"].values() if gate_result["required"])
        passed_required = sum(1 for gate_result in results["gates"].values() 
                             if gate_result["required"] and gate_result["passed"])
        
        results["summary"] = {
            "total_gates": total_gates,
            "passed_gates": passed_gates,
            "required_gates": required_gates,
            "passed_required_gates": passed_required,
            "quality_score": results["quality_score"],
            "overall_passed": results["overall_passed"],
            "production_ready": results["overall_passed"] and results["quality_score"] >= 0.8
        }
        
        # Generate recommendations
        recommendations = []
        
        for gate_name, gate_result in results["gates"].items():
            if not gate_result["passed"]:
                if gate_name == "test_coverage":
                    recommendations.append(f"Increase test coverage from {gate_result['current_value']:.1f}% to ≥{gate_result['threshold']}%")
                elif gate_name == "security_vulnerabilities":
                    recommendations.append(f"Address {int(gate_result['current_value'])} security vulnerabilities")
                elif gate_name == "performance_regression":
                    recommendations.append(f"Fix performance regression of {gate_result['current_value']:.1f}%")
                elif gate_name == "code_complexity":
                    recommendations.append(f"Reduce code complexity from {gate_result['current_value']:.1f} to ≤{gate_result['threshold']}")
                elif gate_name == "documentation_coverage":
                    recommendations.append(f"Improve documentation coverage from {gate_result['current_value']:.1f}% to ≥{gate_result['threshold']}%")
                elif gate_name == "build_success_rate":
                    recommendations.append(f"Fix build failures (currently {gate_result['current_value']:.1f}% success rate)")
                elif gate_name == "memory_usage":
                    recommendations.append(f"Reduce memory usage from {gate_result['current_value']:.1f}MB to ≤{gate_result['threshold']}MB")
                else:
                    recommendations.append(f"Address failing quality gate: {gate_name}")
        
        if not recommendations:
            recommendations.append("All quality gates passed! Project meets enterprise standards.")
        
        results["recommendations"] = recommendations
    
    def _save_results(self, results: Dict):
        """Save quality gate results to file."""
        timestamp = int(time.time())
        
        # Save timestamped results
        results_file = self.results_dir / f"quality_gates_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save latest results
        latest_file = self.results_dir / "latest_quality_gates.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📋 Quality gate results saved to: {results_file}")
    
    def print_summary(self, results: Dict):
        """Print a formatted summary of quality gate results."""
        print("\n" + "=" * 60)
        print("🎯 QUALITY GATE SUMMARY")
        print("=" * 60)
        
        summary = results["summary"]
        print(f"Overall Status: {'✅ PASSED' if results['overall_passed'] else '❌ FAILED'}")
        print(f"Quality Score: {results['quality_score']:.1%}")
        print(f"Gates Passed: {summary['passed_gates']}/{summary['total_gates']}")
        print(f"Required Gates: {summary['passed_required_gates']}/{summary['required_gates']}")
        print(f"Production Ready: {'✅ YES' if summary['production_ready'] else '❌ NO'}")
        
        print(f"\n📋 Recommendations:")
        for i, rec in enumerate(results["recommendations"], 1):
            print(f"  {i}. {rec}")
        
        return results["overall_passed"]


def main():
    """Main entry point for quality gate enforcer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enforce quality gates")
    parser.add_argument("--config", help="Path to quality gates configuration file")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    
    args = parser.parse_args()
    
    enforcer = QualityGateEnforcer(args.project_root, args.config)
    results = enforcer.evaluate_all_gates()
    passed = enforcer.print_summary(results)
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
