#!/usr/bin/env python3
"""
Master Quality Assurance Suite for Protobuf Buck2 Integration.

This script orchestrates the complete QA process including quality gates,
code review automation, security auditing, and production readiness validation.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Import QA components
sys.path.insert(0, str(Path(__file__).parent))
from framework.quality_gates import QualityGateEnforcer
from framework.review_checklist import CodeReviewAutomation
from security.penetration_testing import PenetrationTester


class MasterQARunner:
    """Master Quality Assurance orchestrator."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.qa_dir = self.project_root / "qa"
        self.results_dir = self.qa_dir / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize QA components
        self.quality_gates = QualityGateEnforcer(str(self.project_root))
        self.code_review = CodeReviewAutomation(str(self.project_root))
        self.security_tester = PenetrationTester(str(self.project_root))
    
    def run_complete_qa_suite(self, components: Optional[List[str]] = None) -> Dict:
        """Run the complete quality assurance suite."""
        print("🚀 Starting Complete Quality Assurance Suite")
        print("=" * 70)
        print(f"Project: {self.project_root}")
        print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)
        
        # Default to all components if none specified
        if components is None:
            components = ["quality_gates", "code_review", "security_audit"]
        
        master_results = {
            "timestamp": time.time(),
            "project_root": str(self.project_root),
            "components_run": components,
            "component_results": {},
            "overall_summary": {},
            "production_readiness": {},
            "recommendations": []
        }
        
        # Run Quality Gates
        if "quality_gates" in components:
            print("\n" + "🎯 QUALITY GATES VALIDATION" + "\n")
            gate_results = self.quality_gates.evaluate_all_gates()
            master_results["component_results"]["quality_gates"] = gate_results
            self.quality_gates.print_summary(gate_results)
        
        # Run Code Review Automation  
        if "code_review" in components:
            print("\n" + "🔍 CODE REVIEW AUTOMATION" + "\n")
            review_results = self.code_review.run_automated_review()
            master_results["component_results"]["code_review"] = review_results
            self.code_review.print_review_summary(review_results)
        
        # Run Security Audit
        if "security_audit" in components:
            print("\n" + "🔒 SECURITY PENETRATION TESTING" + "\n")
            security_results = self.security_tester.run_comprehensive_security_audit()
            master_results["component_results"]["security_audit"] = security_results
            self.security_tester.print_security_summary(security_results)
        
        # Generate overall assessment
        self._generate_overall_assessment(master_results)
        
        # Save comprehensive results
        self._save_comprehensive_results(master_results)
        
        # Print final summary
        self._print_final_summary(master_results)
        
        return master_results
    
    def _generate_overall_assessment(self, results: Dict):
        """Generate overall quality assessment."""
        component_results = results["component_results"]
        
        # Extract key metrics from each component
        quality_gates_passed = False
        code_review_approved = False
        security_audit_passed = False
        
        # Quality Gates Assessment
        if "quality_gates" in component_results:
            quality_gates_passed = component_results["quality_gates"]["overall_passed"]
            quality_score = component_results["quality_gates"]["quality_score"]
        else:
            quality_score = 0
        
        # Code Review Assessment
        if "code_review" in component_results:
            code_review_approved = component_results["code_review"]["summary"]["review_approved"]
            review_critical_failures = component_results["code_review"]["summary"]["critical_failures"]
        else:
            review_critical_failures = 0
        
        # Security Assessment
        if "security_audit" in component_results:
            security_audit_passed = component_results["security_audit"]["summary"]["production_ready"]
            security_score = component_results["security_audit"]["security_score"]
            critical_vulns = component_results["security_audit"]["summary"]["critical_vulnerabilities"]
            high_vulns = component_results["security_audit"]["summary"]["high_vulnerabilities"]
        else:
            security_score = 0
            critical_vulns = 0
            high_vulns = 0
        
        # Calculate overall scores
        component_scores = []
        if "quality_gates" in component_results:
            component_scores.append(quality_score)
        if "security_audit" in component_results:
            component_scores.append(security_score)
        if "code_review" in component_results:
            # Convert review success to score
            review_score = 100 if code_review_approved else 50
            component_scores.append(review_score)
        
        overall_score = sum(component_scores) / len(component_scores) if component_scores else 0
        
        # Determine production readiness
        production_ready = (
            quality_gates_passed and
            code_review_approved and 
            security_audit_passed and
            critical_vulns == 0 and
            review_critical_failures == 0
        )
        
        # Determine release readiness level
        if production_ready and overall_score >= 95:
            readiness_level = "PRODUCTION_READY"
            readiness_description = "Ready for immediate production deployment"
        elif production_ready and overall_score >= 90:
            readiness_level = "RELEASE_CANDIDATE"
            readiness_description = "Ready for release with minor improvements"
        elif overall_score >= 80 and critical_vulns == 0:
            readiness_level = "PRE_RELEASE"
            readiness_description = "Needs quality improvements before release"
        elif overall_score >= 60:
            readiness_level = "DEVELOPMENT"
            readiness_description = "Requires significant improvements"
        else:
            readiness_level = "NOT_READY"
            readiness_description = "Major issues must be addressed"
        
        # Store overall summary
        results["overall_summary"] = {
            "overall_score": overall_score,
            "quality_gates_passed": quality_gates_passed,
            "code_review_approved": code_review_approved,
            "security_audit_passed": security_audit_passed,
            "critical_vulnerabilities": critical_vulns,
            "high_vulnerabilities": high_vulns,
            "review_critical_failures": review_critical_failures
        }
        
        results["production_readiness"] = {
            "ready": production_ready,
            "level": readiness_level,
            "description": readiness_description,
            "score": overall_score
        }
        
        # Generate comprehensive recommendations
        recommendations = []
        
        if not quality_gates_passed:
            recommendations.append("CRITICAL: Fix failing quality gates before release")
        
        if not code_review_approved:
            recommendations.append("HIGH: Address code review failures")
        
        if not security_audit_passed:
            recommendations.append("CRITICAL: Fix security vulnerabilities before release")
        
        if critical_vulns > 0:
            recommendations.append(f"CRITICAL: Address {critical_vulns} critical security vulnerabilities")
        
        if high_vulns > 0:
            recommendations.append(f"HIGH: Fix {high_vulns} high-severity security issues")
        
        if overall_score < 90:
            recommendations.append(f"Improve overall quality score from {overall_score:.1f}% to ≥90%")
        
        if not recommendations:
            recommendations.append("All quality checks passed! Project meets enterprise standards.")
        
        results["recommendations"] = recommendations
    
    def _save_comprehensive_results(self, results: Dict):
        """Save comprehensive QA results."""
        timestamp = int(time.time())
        
        # Save timestamped comprehensive report
        report_file = self.results_dir / f"comprehensive_qa_report_{timestamp}.json"
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save latest comprehensive report
        latest_file = self.results_dir / "latest_comprehensive_qa_report.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Create summary file for CI systems
        summary_file = self.results_dir / "qa_summary.json"
        summary_data = {
            "production_ready": results["production_readiness"]["ready"],
            "readiness_level": results["production_readiness"]["level"],
            "overall_score": results["production_readiness"]["score"],
            "timestamp": results["timestamp"],
            "recommendations": results["recommendations"][:3]  # Top 3 recommendations
        }
        with open(summary_file, 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        print(f"\n📋 Comprehensive QA report saved to: {report_file}")
    
    def _print_final_summary(self, results: Dict):
        """Print final comprehensive QA summary."""
        print("\n" + "=" * 70)
        print("🏁 COMPREHENSIVE QUALITY ASSURANCE SUMMARY")
        print("=" * 70)
        
        overall = results["overall_summary"]
        readiness = results["production_readiness"]
        
        # Overall Status
        print(f"Overall Quality Score: {readiness['score']:.1f}%")
        print(f"Production Readiness: {'✅ ' + readiness['level'] if readiness['ready'] else '❌ ' + readiness['level']}")
        print(f"Description: {readiness['description']}")
        
        # Component Status
        print(f"\n📊 Component Status:")
        print(f"  Quality Gates: {'✅ PASSED' if overall['quality_gates_passed'] else '❌ FAILED'}")
        print(f"  Code Review: {'✅ APPROVED' if overall['code_review_approved'] else '❌ NEEDS WORK'}")
        print(f"  Security Audit: {'✅ PASSED' if overall['security_audit_passed'] else '❌ FAILED'}")
        
        # Critical Issues
        critical_issues = (
            overall['critical_vulnerabilities'] + 
            overall['review_critical_failures']
        )
        
        if critical_issues > 0:
            print(f"\n🚨 Critical Issues: {critical_issues}")
            print(f"  Security Critical: {overall['critical_vulnerabilities']}")
            print(f"  Review Critical: {overall['review_critical_failures']}")
        else:
            print(f"\n✅ No Critical Issues Found")
        
        # High Priority Issues
        high_issues = overall['high_vulnerabilities']
        if high_issues > 0:
            print(f"⚠️  High Priority Issues: {high_issues}")
        
        # Top Recommendations
        if results["recommendations"]:
            print(f"\n📋 Top Recommendations:")
            for i, rec in enumerate(results["recommendations"][:5], 1):
                print(f"  {i}. {rec}")
        
        # Final Verdict
        print(f"\n" + "=" * 70)
        if readiness["ready"]:
            print("🎉 QUALITY ASSURANCE PASSED - READY FOR PRODUCTION!")
        else:
            print("⚠️  QUALITY ASSURANCE FAILED - IMPROVEMENTS REQUIRED")
        print("=" * 70)
        
        return readiness["ready"]
    
    def run_quick_qa_check(self) -> Dict:
        """Run a quick QA check for CI/CD pipelines."""
        print("⚡ Running Quick QA Check")
        print("=" * 40)
        
        # Run essential checks only
        gate_results = self.quality_gates.evaluate_all_gates()
        
        # Quick assessment
        quick_results = {
            "timestamp": time.time(),
            "quick_check": True,
            "quality_gates_passed": gate_results["overall_passed"],
            "quality_score": gate_results["quality_score"],
            "production_ready": gate_results["overall_passed"] and gate_results["quality_score"] >= 0.8
        }
        
        print(f"Quality Score: {gate_results['quality_score']:.1%}")
        print(f"Production Ready: {'✅ YES' if quick_results['production_ready'] else '❌ NO'}")
        
        return quick_results


def main():
    """Main entry point for QA suite."""
    parser = argparse.ArgumentParser(description="Run comprehensive quality assurance suite")
    parser.add_argument(
        "--components",
        nargs="+",
        choices=["quality_gates", "code_review", "security_audit", "all"],
        default=["all"],
        help="QA components to run"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick QA check (quality gates only)"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root directory"
    )
    
    args = parser.parse_args()
    
    # Determine components to run
    if args.quick:
        # Quick mode runs only essential checks
        runner = MasterQARunner(args.project_root)
        results = runner.run_quick_qa_check()
        production_ready = results["production_ready"]
    else:
        # Full QA suite
        if "all" in args.components:
            components = ["quality_gates", "code_review", "security_audit"]
        else:
            components = args.components
        
        runner = MasterQARunner(args.project_root)
        results = runner.run_complete_qa_suite(components)
        production_ready = results["production_readiness"]["ready"]
    
    # Exit with appropriate code for CI/CD
    sys.exit(0 if production_ready else 1)


if __name__ == "__main__":
    main()
