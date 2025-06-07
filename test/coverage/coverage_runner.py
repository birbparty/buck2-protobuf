#!/usr/bin/env python3
"""
Comprehensive test coverage measurement for protobuf Buck2 integration.

This module provides comprehensive coverage measurement across all test types
including unit tests, integration tests, and performance benchmarks.
"""

import os
import sys
import subprocess
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import coverage
import unittest


class CoverageRunner:
    """Runs comprehensive test coverage analysis."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.coverage_dir = self.project_root / "test" / "coverage"
        self.coverage_dir.mkdir(parents=True, exist_ok=True)
        
        # Coverage configuration
        self.cov = coverage.Coverage(
            source=[
                str(self.project_root / "rules"),
                str(self.project_root / "tools"),
            ],
            omit=[
                "*/test/*",
                "*/tests/*",
                "*/__pycache__/*",
                "*/.*",
            ],
            config_file=str(self.coverage_dir / ".coveragerc")
        )
        
        # Test results tracking
        self.results = {
            "unit_tests": {},
            "integration_tests": {},
            "performance_tests": {},
            "cross_language_tests": {},
            "overall_coverage": {},
            "quality_metrics": {}
        }
    
    def setup_coverage_config(self):
        """Create coverage configuration file."""
        config_content = """
[run]
branch = True
source = rules, tools
omit = 
    */test/*
    */tests/*
    */__pycache__/*
    */.*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    if self.debug:
    if settings.DEBUG
    raise AssertionError
    raise NotImplementedError
    if 0:
    if __name__ == .__main__.:

[html]
directory = test/coverage/htmlcov

[xml]
output = test/coverage/coverage.xml
"""
        config_path = self.coverage_dir / ".coveragerc"
        with open(config_path, "w") as f:
            f.write(config_content.strip())
    
    def run_unit_tests_with_coverage(self) -> Dict:
        """Run unit tests with coverage measurement."""
        print("🧪 Running unit tests with coverage...")
        
        self.cov.start()
        
        # Discover and run unit tests
        test_suite = unittest.TestLoader().discover(
            str(self.project_root / "test" / "rules"),
            pattern="*_test.py"
        )
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(test_suite)
        
        self.cov.stop()
        self.cov.save()
        
        # Generate coverage report
        coverage_data = self._generate_coverage_report()
        
        unit_results = {
            "tests_run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "success_rate": (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun if result.testsRun > 0 else 0,
            "coverage": coverage_data
        }
        
        self.results["unit_tests"] = unit_results
        return unit_results
    
    def run_integration_tests(self) -> Dict:
        """Run integration tests."""
        print("🔧 Running integration tests...")
        
        integration_script = self.project_root / "test" / "integration" / "test_workflows.sh"
        
        start_time = time.time()
        result = subprocess.run(
            ["bash", str(integration_script)],
            cwd=self.project_root,
            capture_output=True,
            text=True
        )
        duration = time.time() - start_time
        
        integration_results = {
            "exit_code": result.returncode,
            "duration_seconds": duration,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0
        }
        
        self.results["integration_tests"] = integration_results
        return integration_results
    
    def run_performance_benchmarks(self) -> Dict:
        """Run performance benchmark tests."""
        print("⚡ Running performance benchmarks...")
        
        benchmarks = [
            self._benchmark_small_proto,
            self._benchmark_medium_proto,
            self._benchmark_large_proto,
            self._benchmark_incremental_build,
            self._benchmark_cache_performance
        ]
        
        performance_results = {}
        
        for benchmark in benchmarks:
            name = benchmark.__name__.replace("_benchmark_", "")
            try:
                result = benchmark()
                performance_results[name] = result
                print(f"  ✓ {name}: {result.get('duration_ms', 0):.0f}ms")
            except Exception as e:
                performance_results[name] = {"error": str(e)}
                print(f"  ✗ {name}: {e}")
        
        self.results["performance_tests"] = performance_results
        return performance_results
    
    def run_cross_language_tests(self) -> Dict:
        """Run cross-language compatibility tests."""
        print("🌐 Running cross-language compatibility tests...")
        
        languages = ["go", "python", "typescript", "cpp", "rust"]
        compatibility_matrix = {}
        
        for lang in languages:
            compatibility_matrix[lang] = {}
            for other_lang in languages:
                if lang != other_lang:
                    result = self._test_language_compatibility(lang, other_lang)
                    compatibility_matrix[lang][other_lang] = result
        
        cross_lang_results = {
            "compatibility_matrix": compatibility_matrix,
            "overall_compatibility": self._calculate_overall_compatibility(compatibility_matrix)
        }
        
        self.results["cross_language_tests"] = cross_lang_results
        return cross_lang_results
    
    def run_mutation_testing(self) -> Dict:
        """Run mutation testing for test quality assessment."""
        print("🧬 Running mutation testing...")
        
        try:
            # Use mutmut for mutation testing
            result = subprocess.run(
                ["mutmut", "run", "--paths-to-mutate", "rules/"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            # Get mutation testing results
            results_result = subprocess.run(
                ["mutmut", "results"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            mutation_results = {
                "available": True,
                "results": results_result.stdout,
                "stderr": results_result.stderr
            }
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            mutation_results = {
                "available": False,
                "error": "Mutation testing not available or timed out"
            }
        
        return mutation_results
    
    def generate_comprehensive_report(self) -> Dict:
        """Generate comprehensive test report."""
        print("📊 Generating comprehensive test report...")
        
        # Calculate overall metrics
        overall_coverage = self.results.get("unit_tests", {}).get("coverage", {})
        coverage_percentage = overall_coverage.get("percent_covered", 0)
        
        # Performance target validation
        performance_targets = {
            "small_proto": 2000,  # 2s
            "medium_proto": 10000,  # 10s  
            "large_proto": 30000,  # 30s
            "incremental_build": 500,  # 500ms
            "cache_performance": 100  # 100ms
        }
        
        performance_results = self.results.get("performance_tests", {})
        performance_pass = True
        
        for test_name, target_ms in performance_targets.items():
            actual_ms = performance_results.get(test_name, {}).get("duration_ms", float('inf'))
            if actual_ms > target_ms:
                performance_pass = False
                break
        
        # Cross-language compatibility
        cross_lang_results = self.results.get("cross_language_tests", {})
        compatibility_score = cross_lang_results.get("overall_compatibility", 0)
        
        comprehensive_report = {
            "timestamp": time.time(),
            "summary": {
                "coverage_percentage": coverage_percentage,
                "coverage_target_met": coverage_percentage >= 95,
                "performance_targets_met": performance_pass,
                "cross_language_compatibility": compatibility_score,
                "overall_quality_score": self._calculate_quality_score()
            },
            "detailed_results": self.results,
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        report_path = self.coverage_dir / "comprehensive_report.json"
        with open(report_path, "w") as f:
            json.dump(comprehensive_report, f, indent=2)
        
        return comprehensive_report
    
    def _generate_coverage_report(self) -> Dict:
        """Generate detailed coverage report."""
        # Generate HTML report
        html_dir = self.coverage_dir / "htmlcov"
        self.cov.html_report(directory=str(html_dir))
        
        # Generate XML report
        xml_path = self.coverage_dir / "coverage.xml"
        self.cov.xml_report(outfile=str(xml_path))
        
        # Get coverage statistics
        total_lines = 0
        covered_lines = 0
        
        for filename in self.cov.get_data().measured_files():
            analysis = self.cov.analysis2(filename)
            total_lines += len(analysis.statements)
            covered_lines += len(analysis.statements) - len(analysis.missing)
        
        percent_covered = (covered_lines / total_lines * 100) if total_lines > 0 else 0
        
        return {
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "percent_covered": percent_covered,
            "html_report": str(html_dir),
            "xml_report": str(xml_path)
        }
    
    def _benchmark_small_proto(self) -> Dict:
        """Benchmark small proto compilation."""
        return self._run_buck_benchmark(
            "//test/fixtures/basic:minimal_proto",
            target_ms=2000
        )
    
    def _benchmark_medium_proto(self) -> Dict:
        """Benchmark medium proto compilation."""
        return self._run_buck_benchmark(
            "//test/fixtures/basic:types_proto",
            target_ms=10000
        )
    
    def _benchmark_large_proto(self) -> Dict:
        """Benchmark large proto compilation."""
        return self._run_buck_benchmark(
            "//test/fixtures/performance:large_proto",
            target_ms=30000
        )
    
    def _benchmark_incremental_build(self) -> Dict:
        """Benchmark incremental build performance."""
        # First build
        subprocess.run(
            ["buck2", "build", "//test/fixtures/basic:minimal_proto"],
            cwd=self.project_root,
            capture_output=True
        )
        
        # Second build (should be incremental)
        start_time = time.time()
        result = subprocess.run(
            ["buck2", "build", "//test/fixtures/basic:minimal_proto"],
            cwd=self.project_root,
            capture_output=True
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return {
            "duration_ms": duration_ms,
            "target_ms": 500,
            "success": result.returncode == 0 and duration_ms <= 500
        }
    
    def _benchmark_cache_performance(self) -> Dict:
        """Benchmark cache hit performance."""
        # Ensure cache is populated
        subprocess.run(
            ["buck2", "build", "//test/fixtures:simple_proto"],
            cwd=self.project_root,
            capture_output=True
        )
        
        # Measure cache hit time
        start_time = time.time()
        result = subprocess.run(
            ["buck2", "build", "//test/fixtures:simple_proto"],
            cwd=self.project_root,
            capture_output=True
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return {
            "duration_ms": duration_ms,
            "target_ms": 100,
            "success": result.returncode == 0 and duration_ms <= 100
        }
    
    def _run_buck_benchmark(self, target: str, target_ms: int) -> Dict:
        """Run a Buck2 build benchmark."""
        # Clean first
        subprocess.run(["buck2", "clean"], cwd=self.project_root, capture_output=True)
        
        # Measure build time
        start_time = time.time()
        result = subprocess.run(
            ["buck2", "build", target],
            cwd=self.project_root,
            capture_output=True
        )
        duration_ms = (time.time() - start_time) * 1000
        
        return {
            "duration_ms": duration_ms,
            "target_ms": target_ms,
            "success": result.returncode == 0 and duration_ms <= target_ms,
            "stdout": result.stdout.decode() if result.stdout else "",
            "stderr": result.stderr.decode() if result.stderr else ""
        }
    
    def _test_language_compatibility(self, lang1: str, lang2: str) -> Dict:
        """Test compatibility between two languages."""
        try:
            # Build proto for both languages
            target1 = f"//examples/{lang1}:user_proto_{lang1}"
            target2 = f"//examples/{lang2}:user_proto_{lang2}"
            
            result1 = subprocess.run(
                ["buck2", "build", target1],
                cwd=self.project_root,
                capture_output=True
            )
            
            result2 = subprocess.run(
                ["buck2", "build", target2],
                cwd=self.project_root,
                capture_output=True
            )
            
            compatible = result1.returncode == 0 and result2.returncode == 0
            
            return {
                "compatible": compatible,
                "lang1_success": result1.returncode == 0,
                "lang2_success": result2.returncode == 0
            }
            
        except Exception as e:
            return {
                "compatible": False,
                "error": str(e)
            }
    
    def _calculate_overall_compatibility(self, matrix: Dict) -> float:
        """Calculate overall compatibility score."""
        total_tests = 0
        passed_tests = 0
        
        for lang1, lang1_results in matrix.items():
            for lang2, result in lang1_results.items():
                total_tests += 1
                if result.get("compatible", False):
                    passed_tests += 1
        
        return (passed_tests / total_tests) if total_tests > 0 else 0
    
    def _calculate_quality_score(self) -> float:
        """Calculate overall quality score."""
        scores = []
        
        # Coverage score
        coverage_pct = self.results.get("unit_tests", {}).get("coverage", {}).get("percent_covered", 0)
        scores.append(min(coverage_pct / 95, 1.0))  # Normalize to 95% target
        
        # Performance score
        performance_results = self.results.get("performance_tests", {})
        performance_score = 0
        performance_count = 0
        
        targets = {"small_proto": 2000, "medium_proto": 10000, "large_proto": 30000}
        for test_name, target_ms in targets.items():
            if test_name in performance_results:
                actual_ms = performance_results[test_name].get("duration_ms", float('inf'))
                score = max(0, min(1, (target_ms - actual_ms) / target_ms + 1))
                performance_score += score
                performance_count += 1
        
        if performance_count > 0:
            scores.append(performance_score / performance_count)
        
        # Compatibility score
        compat_score = self.results.get("cross_language_tests", {}).get("overall_compatibility", 0)
        scores.append(compat_score)
        
        return sum(scores) / len(scores) if scores else 0
    
    def _generate_recommendations(self) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        # Coverage recommendations
        coverage_pct = self.results.get("unit_tests", {}).get("coverage", {}).get("percent_covered", 0)
        if coverage_pct < 95:
            recommendations.append(f"Increase test coverage from {coverage_pct:.1f}% to >95%")
        
        # Performance recommendations
        performance_results = self.results.get("performance_tests", {})
        targets = {"small_proto": 2000, "medium_proto": 10000, "large_proto": 30000}
        
        for test_name, target_ms in targets.items():
            if test_name in performance_results:
                actual_ms = performance_results[test_name].get("duration_ms", 0)
                if actual_ms > target_ms:
                    recommendations.append(f"Optimize {test_name} performance: {actual_ms:.0f}ms > {target_ms}ms target")
        
        # Compatibility recommendations
        compat_score = self.results.get("cross_language_tests", {}).get("overall_compatibility", 0)
        if compat_score < 1.0:
            recommendations.append(f"Improve cross-language compatibility: {compat_score:.1%}")
        
        return recommendations


def main():
    """Main entry point for coverage runner."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    runner = CoverageRunner(project_root)
    runner.setup_coverage_config()
    
    print("🚀 Starting comprehensive test suite...")
    
    # Run all test categories
    runner.run_unit_tests_with_coverage()
    runner.run_integration_tests()
    runner.run_performance_benchmarks()
    runner.run_cross_language_tests()
    
    # Generate comprehensive report
    report = runner.generate_comprehensive_report()
    
    # Print summary
    summary = report["summary"]
    print("\n📊 Test Suite Summary:")
    print(f"  Coverage: {summary['coverage_percentage']:.1f}% (Target: ≥95%)")
    print(f"  Performance Targets: {'✓' if summary['performance_targets_met'] else '✗'}")
    print(f"  Cross-Language Compatibility: {summary['cross_language_compatibility']:.1%}")
    print(f"  Overall Quality Score: {summary['overall_quality_score']:.1%}")
    
    # Check if targets met
    targets_met = (
        summary['coverage_target_met'] and
        summary['performance_targets_met'] and
        summary['cross_language_compatibility'] >= 0.95
    )
    
    if targets_met:
        print("\n🎉 All quality targets met!")
        sys.exit(0)
    else:
        print("\n⚠️  Quality targets not met. See recommendations in report.")
        sys.exit(1)


if __name__ == "__main__":
    main()
