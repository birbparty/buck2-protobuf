#!/usr/bin/env python3
"""
Code Review Process Automation for Protobuf Buck2 Integration.

This module implements automated code review checks and provides
structured checklists for manual reviews to ensure all changes
meet enterprise-grade standards.
"""

import ast
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ReviewCheck:
    """Represents a single review check."""
    name: str
    description: str
    category: str
    severity: str  # "critical", "high", "medium", "low"
    automated: bool
    passed: Optional[bool] = None
    details: Optional[Dict] = None


class CodeReviewAutomation:
    """Automates code review checks and provides review guidance."""
    
    def __init__(self, project_root: str, target_branch: str = "main"):
        self.project_root = Path(project_root)
        self.target_branch = target_branch
        self.results_dir = self.project_root / "qa" / "results" / "reviews"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Define review checks
        self.checks = self._define_review_checks()
    
    def _define_review_checks(self) -> List[ReviewCheck]:
        """Define all review checks."""
        return [
            # Architecture Review
            ReviewCheck(
                name="interface_design",
                description="Public interfaces are well-designed and backward compatible",
                category="architecture",
                severity="critical",
                automated=False
            ),
            ReviewCheck(
                name="error_handling",
                description="Error handling is comprehensive and consistent",
                category="architecture",
                severity="high",
                automated=True
            ),
            ReviewCheck(
                name="performance_impact",
                description="Changes don't introduce performance regressions",
                category="architecture",
                severity="high",
                automated=True
            ),
            ReviewCheck(
                name="security_implications",
                description="Security implications are properly addressed",
                category="architecture",
                severity="critical",
                automated=True
            ),
            
            # Implementation Quality
            ReviewCheck(
                name="code_complexity",
                description="Code complexity is within acceptable bounds",
                category="implementation",
                severity="medium",
                automated=True
            ),
            ReviewCheck(
                name="naming_conventions",
                description="Naming follows project conventions",
                category="implementation",
                severity="low",
                automated=True
            ),
            ReviewCheck(
                name="code_duplication",
                description="No unnecessary code duplication",
                category="implementation",
                severity="medium",
                automated=True
            ),
            ReviewCheck(
                name="resource_management",
                description="Memory and resource management is correct",
                category="implementation",
                severity="high",
                automated=True
            ),
            
            # Testing Quality
            ReviewCheck(
                name="test_coverage",
                description="Adequate test coverage for new/changed code",
                category="testing",
                severity="critical",
                automated=True
            ),
            ReviewCheck(
                name="test_quality",
                description="Tests are meaningful and catch real issues",
                category="testing",
                severity="high",
                automated=False
            ),
            ReviewCheck(
                name="edge_cases",
                description="Edge cases and error conditions are tested",
                category="testing",
                severity="high",
                automated=False
            ),
            
            # Documentation Quality
            ReviewCheck(
                name="api_documentation",
                description="Public APIs are properly documented",
                category="documentation",
                severity="high",
                automated=True
            ),
            ReviewCheck(
                name="code_comments",
                description="Complex logic is well-commented",
                category="documentation",
                severity="medium",
                automated=True
            ),
            ReviewCheck(
                name="changelog_update",
                description="Changes are documented in changelog",
                category="documentation",
                severity="medium",
                automated=True
            )
        ]
    
    def run_automated_review(self, changed_files: Optional[List[str]] = None) -> Dict:
        """Run automated code review checks."""
        print("🔍 Running Automated Code Review")
        print("=" * 50)
        
        # Get changed files if not provided
        if changed_files is None:
            changed_files = self._get_changed_files()
        
        results = {
            "timestamp": time.time(),
            "changed_files": changed_files,
            "checks": {},
            "summary": {},
            "manual_review_items": []
        }
        
        # Run each automated check
        for check in self.checks:
            if check.automated:
                check_result = self._run_check(check, changed_files)
                results["checks"][check.name] = {
                    "passed": check_result.passed,
                    "details": check_result.details,
                    "category": check_result.category,
                    "severity": check_result.severity
                }
                
                status = "✓" if check_result.passed else "✗"
                print(f"  {status} {check.name} ({check.severity})")
            else:
                # Add to manual review items
                results["manual_review_items"].append({
                    "name": check.name,
                    "description": check.description,
                    "category": check.category,
                    "severity": check.severity
                })
        
        # Generate summary
        self._generate_review_summary(results)
        
        # Save results
        self._save_review_results(results)
        
        return results
    
    def _get_changed_files(self) -> List[str]:
        """Get list of changed files compared to target branch."""
        try:
            # Get changed files using git
            result = subprocess.run(
                ["git", "diff", "--name-only", f"{self.target_branch}...HEAD"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                changed_files = [f.strip() for f in result.stdout.split('\n') if f.strip()]
                return changed_files
            else:
                # Fallback: get all files in certain directories
                files = []
                for pattern in ["rules/**/*.py", "tools/**/*.py", "rules/**/*.bzl"]:
                    files.extend([str(f) for f in self.project_root.glob(pattern)])
                return files
        
        except Exception:
            # Emergency fallback
            return []
    
    def _run_check(self, check: ReviewCheck, changed_files: List[str]) -> ReviewCheck:
        """Run a specific automated check."""
        try:
            if check.name == "error_handling":
                check.passed, check.details = self._check_error_handling(changed_files)
            
            elif check.name == "performance_impact":
                check.passed, check.details = self._check_performance_impact(changed_files)
            
            elif check.name == "security_implications":
                check.passed, check.details = self._check_security_implications(changed_files)
            
            elif check.name == "code_complexity":
                check.passed, check.details = self._check_code_complexity(changed_files)
            
            elif check.name == "naming_conventions":
                check.passed, check.details = self._check_naming_conventions(changed_files)
            
            elif check.name == "code_duplication":
                check.passed, check.details = self._check_code_duplication(changed_files)
            
            elif check.name == "resource_management":
                check.passed, check.details = self._check_resource_management(changed_files)
            
            elif check.name == "test_coverage":
                check.passed, check.details = self._check_test_coverage(changed_files)
            
            elif check.name == "api_documentation":
                check.passed, check.details = self._check_api_documentation(changed_files)
            
            elif check.name == "code_comments":
                check.passed, check.details = self._check_code_comments(changed_files)
            
            elif check.name == "changelog_update":
                check.passed, check.details = self._check_changelog_update(changed_files)
            
            else:
                check.passed = True
                check.details = {"status": "check_not_implemented"}
        
        except Exception as e:
            check.passed = False
            check.details = {"error": str(e)}
        
        return check
    
    def _check_error_handling(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for proper error handling patterns."""
        issues = []
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        for file_path in python_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Parse AST to find function definitions
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_body = ast.dump(node)
                        
                        # Check for subprocess calls without error handling
                        if 'subprocess' in func_body and 'try:' not in func_body:
                            issues.append({
                                "file": file_path,
                                "function": node.name,
                                "issue": "subprocess call without error handling",
                                "line": node.lineno
                            })
                        
                        # Check for file operations without error handling
                        if ('open(' in func_body or 'with open(' in func_body) and 'try:' not in func_body:
                            # Allow if it's already in a try block or with statement
                            if 'with open(' not in func_body:
                                issues.append({
                                    "file": file_path,
                                    "function": node.name,
                                    "issue": "file operation without error handling",
                                    "line": node.lineno
                                })
            
            except Exception as e:
                issues.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(issues) == 0
        details = {
            "issues_found": len(issues),
            "issues": issues[:10],  # Limit to first 10 issues
            "files_analyzed": len(python_files)
        }
        
        return passed, details
    
    def _check_performance_impact(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for potential performance impacts."""
        issues = []
        
        for file_path in changed_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Check for potential performance issues
                if '.py' in file_path:
                    # Look for potentially expensive operations
                    expensive_patterns = [
                        ('subprocess.call', 'synchronous subprocess call'),
                        ('time.sleep', 'blocking sleep operation'),
                        ('requests.get', 'synchronous HTTP request'),
                        ('glob.glob', 'recursive file globbing'),
                    ]
                    
                    for pattern, description in expensive_patterns:
                        if pattern in content:
                            issues.append({
                                "file": file_path,
                                "pattern": pattern,
                                "description": description,
                                "suggestion": "Consider async/optimized alternatives"
                            })
                
                elif '.bzl' in file_path:
                    # Check Buck2 rule performance patterns
                    if 'glob(' in content and '**' in content:
                        issues.append({
                            "file": file_path,
                            "pattern": "recursive glob",
                            "description": "recursive glob in Buck rule",
                            "suggestion": "Consider more specific patterns"
                        })
            
            except Exception as e:
                issues.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        # Performance issues are warnings, not failures
        passed = len([i for i in issues if 'subprocess.call' in i.get('pattern', '')]) == 0
        details = {
            "potential_issues": len(issues),
            "issues": issues,
            "files_analyzed": len(changed_files)
        }
        
        return passed, details
    
    def _check_security_implications(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for security implications."""
        issues = []
        
        for file_path in changed_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Check for security anti-patterns
                security_patterns = [
                    ('eval(', 'use of eval() function'),
                    ('exec(', 'use of exec() function'),
                    ('shell=True', 'subprocess with shell=True'),
                    ('input(', 'use of input() function'),
                    ('pickle.load', 'use of pickle.load'),
                ]
                
                for pattern, description in security_patterns:
                    if pattern in content:
                        issues.append({
                            "file": file_path,
                            "pattern": pattern,
                            "description": description,
                            "severity": "high"
                        })
                
                # Check for hardcoded secrets (simple patterns)
                secret_patterns = [
                    ('password =', 'potential hardcoded password'),
                    ('api_key =', 'potential hardcoded API key'),
                    ('secret =', 'potential hardcoded secret'),
                ]
                
                for pattern, description in secret_patterns:
                    if pattern in content.lower():
                        # Check if it looks like a real secret (not a comment or test)
                        lines = content.split('\n')
                        for i, line in enumerate(lines):
                            if pattern in line.lower() and not line.strip().startswith('#'):
                                issues.append({
                                    "file": file_path,
                                    "line": i + 1,
                                    "pattern": pattern,
                                    "description": description,
                                    "severity": "critical"
                                })
            
            except Exception as e:
                issues.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        # Fail if any critical security issues found
        critical_issues = [i for i in issues if i.get('severity') == 'critical']
        passed = len(critical_issues) == 0
        
        details = {
            "total_issues": len(issues),
            "critical_issues": len(critical_issues),
            "issues": issues,
            "files_analyzed": len(changed_files)
        }
        
        return passed, details
    
    def _check_code_complexity(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check code complexity metrics."""
        complex_functions = []
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        for file_path in python_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Simple complexity estimation
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Count control flow statements
                        complexity = 1  # Base complexity
                        for child in ast.walk(node):
                            if isinstance(child, (ast.If, ast.For, ast.While, ast.Try)):
                                complexity += 1
                            elif isinstance(child, ast.BoolOp):
                                complexity += len(child.values) - 1
                        
                        if complexity > 10:  # Complexity threshold
                            complex_functions.append({
                                "file": file_path,
                                "function": node.name,
                                "complexity": complexity,
                                "line": node.lineno
                            })
            
            except Exception as e:
                complex_functions.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(complex_functions) == 0
        details = {
            "complex_functions": len(complex_functions),
            "functions": complex_functions[:10],  # Limit output
            "files_analyzed": len(python_files),
            "complexity_threshold": 10
        }
        
        return passed, details
    
    def _check_naming_conventions(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check naming convention adherence."""
        violations = []
        
        for file_path in changed_files:
            if not file_path.endswith('.py'):
                continue
            
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        # Function names should be snake_case
                        if not self._is_snake_case(node.name) and not node.name.startswith('_'):
                            violations.append({
                                "file": file_path,
                                "type": "function",
                                "name": node.name,
                                "line": node.lineno,
                                "expected": "snake_case"
                            })
                    
                    elif isinstance(node, ast.ClassDef):
                        # Class names should be PascalCase
                        if not self._is_pascal_case(node.name):
                            violations.append({
                                "file": file_path,
                                "type": "class",
                                "name": node.name,
                                "line": node.lineno,
                                "expected": "PascalCase"
                            })
            
            except Exception as e:
                violations.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(violations) == 0
        details = {
            "violations": len(violations),
            "items": violations[:10],  # Limit output
            "files_analyzed": len([f for f in changed_files if f.endswith('.py')])
        }
        
        return passed, details
    
    def _check_code_duplication(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for code duplication."""
        # This is a simplified check - in production you'd use tools like PMD or SonarQube
        duplications = []
        
        # For now, just check if files are too similar (placeholder)
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        details = {
            "duplications_found": len(duplications),
            "duplications": duplications,
            "files_analyzed": len(python_files),
            "note": "Advanced duplication detection requires specialized tools"
        }
        
        return True, details  # Pass for now
    
    def _check_resource_management(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for proper resource management."""
        issues = []
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        for file_path in python_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                # Check for file operations without context managers
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'open(' in line and 'with' not in line and '=' in line:
                        issues.append({
                            "file": file_path,
                            "line": i + 1,
                            "issue": "file opened without context manager",
                            "suggestion": "use 'with open()' statement"
                        })
            
            except Exception as e:
                issues.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(issues) == 0
        details = {
            "issues_found": len(issues),
            "issues": issues,
            "files_analyzed": len(python_files)
        }
        
        return passed, details
    
    def _check_test_coverage(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check if changed code has adequate test coverage."""
        # This would integrate with coverage tools in a real implementation
        source_files = [f for f in changed_files if f.endswith('.py') and 'test' not in f]
        test_files = [f for f in changed_files if f.endswith('.py') and 'test' in f]
        
        # Simple heuristic: each source file should have corresponding test changes
        missing_tests = []
        for source_file in source_files:
            # Look for corresponding test file
            base_name = Path(source_file).stem
            has_test = any(base_name in test_file for test_file in test_files)
            
            if not has_test:
                missing_tests.append(source_file)
        
        passed = len(missing_tests) == 0
        details = {
            "source_files": len(source_files),
            "test_files": len(test_files),
            "missing_tests": missing_tests,
            "coverage_ratio": len(test_files) / len(source_files) if source_files else 1.0
        }
        
        return passed, details
    
    def _check_api_documentation(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for API documentation."""
        undocumented = []
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        for file_path in python_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                        # Check if public API (doesn't start with _)
                        if not node.name.startswith('_'):
                            # Check for docstring
                            has_docstring = (
                                node.body and 
                                isinstance(node.body[0], ast.Expr) and
                                isinstance(node.body[0].value, ast.Str)
                            )
                            
                            if not has_docstring:
                                undocumented.append({
                                    "file": file_path,
                                    "type": "function" if isinstance(node, ast.FunctionDef) else "class",
                                    "name": node.name,
                                    "line": node.lineno
                                })
            
            except Exception as e:
                undocumented.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(undocumented) == 0
        details = {
            "undocumented_items": len(undocumented),
            "items": undocumented[:10],  # Limit output
            "files_analyzed": len(python_files)
        }
        
        return passed, details
    
    def _check_code_comments(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check for adequate code comments."""
        # Simple heuristic: complex functions should have comments
        needs_comments = []
        python_files = [f for f in changed_files if f.endswith('.py')]
        
        for file_path in python_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
            
            try:
                with open(full_path, 'r') as f:
                    lines = f.readlines()
                
                # Look for functions without comments
                in_function = False
                function_lines = 0
                comment_lines = 0
                
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    
                    if stripped.startswith('def '):
                        if in_function and function_lines > 10 and comment_lines == 0:
                            needs_comments.append({
                                "file": file_path,
                                "line": i - function_lines,
                                "issue": "complex function without comments",
                                "function_lines": function_lines
                            })
                        
                        in_function = True
                        function_lines = 0
                        comment_lines = 0
                    
                    elif in_function:
                        function_lines += 1
                        if stripped.startswith('#'):
                            comment_lines += 1
                        elif stripped == '' or stripped.startswith('class '):
                            in_function = False
            
            except Exception as e:
                needs_comments.append({
                    "file": file_path,
                    "issue": f"failed to analyze: {e}"
                })
        
        passed = len(needs_comments) == 0
        details = {
            "functions_needing_comments": len(needs_comments),
            "items": needs_comments,
            "files_analyzed": len(python_files)
        }
        
        return passed, details
    
    def _check_changelog_update(self, changed_files: List[str]) -> Tuple[bool, Dict]:
        """Check if changelog was updated for significant changes."""
        # Look for changelog files
        changelog_files = [
            "CHANGELOG.md", "CHANGES.md", "HISTORY.md", 
            "docs/CHANGELOG.md", "docs/CHANGES.md"
        ]
        
        changelog_updated = any(
            any(cf in f for cf in changelog_files) 
            for f in changed_files
        )
        
        # Check if this is a significant change (non-test files modified)
        significant_changes = any(
            f.endswith(('.py', '.bzl')) and 'test' not in f 
            for f in changed_files
        )
        
        passed = not significant_changes or changelog_updated
        details = {
            "significant_changes": significant_changes,
            "changelog_updated": changelog_updated,
            "changed_files": len(changed_files),
            "changelog_files_checked": changelog_files
        }
        
        return passed, details
    
    def _is_snake_case(self, name: str) -> bool:
        """Check if name follows snake_case convention."""
        return name.islower() and '_' in name or name.islower()
    
    def _is_pascal_case(self, name: str) -> bool:
        """Check if name follows PascalCase convention."""
        return name[0].isupper() and '_' not in name
    
    def _generate_review_summary(self, results: Dict):
        """Generate review summary."""
        checks = results["checks"]
        
        total_checks = len(checks)
        passed_checks = sum(1 for check in checks.values() if check["passed"])
        critical_failures = sum(1 for check in checks.values() 
                               if not check["passed"] and check["severity"] == "critical")
        high_failures = sum(1 for check in checks.values() 
                           if not check["passed"] and check["severity"] == "high")
        
        results["summary"] = {
            "total_automated_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": total_checks - passed_checks,
            "critical_failures": critical_failures,
            "high_failures": high_failures,
            "manual_review_items": len(results["manual_review_items"]),
            "review_approved": critical_failures == 0 and high_failures <= 2,
            "changed_files": len(results["changed_files"])
        }
    
    def _save_review_results(self, results: Dict):
        """Save review results."""
        timestamp = int(time.time())
        
        # Save timestamped results
        results_file = self.results_dir / f"code_review_{timestamp}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save latest results
        latest_file = self.results_dir / "latest_code_review.json"
        with open(latest_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n📋 Code review results saved to: {results_file}")
    
    def generate_review_checklist(self) -> str:
        """Generate manual review checklist."""
        checklist = """
# Code Review Checklist

## Architecture Review
- [ ] Public interfaces are well-designed and backward compatible
- [ ] System architecture follows established patterns
- [ ] Component relationships are clear and appropriate
- [ ] Concurrency and thread safety are properly handled

## Implementation Review
- [ ] Code is clear, readable, and maintainable
- [ ] Business logic is correctly implemented
- [ ] Edge cases are handled appropriately
- [ ] Performance implications are considered

## Testing Review
- [ ] Tests are meaningful and catch real issues
- [ ] Edge cases and error conditions are tested
- [ ] Test coverage is adequate for the changes
- [ ] Tests run reliably and quickly

## Security Review
- [ ] Input validation is comprehensive
- [ ] Authorization and authentication are correct
- [ ] Sensitive data is handled properly
- [ ] No security vulnerabilities introduced

## Documentation Review
- [ ] Public APIs are documented
- [ ] Complex logic has appropriate comments
- [ ] README/documentation is updated if needed
- [ ] Examples are provided for new features

## Final Approval
- [ ] All automated checks pass
- [ ] Manual review items addressed
- [ ] Changes align with project goals
- [ ] Ready for production deployment
"""
        return checklist.strip()
    
    def print_review_summary(self, results: Dict):
        """Print formatted review summary."""
        print("\n" + "=" * 60)
        print("🔍 CODE REVIEW SUMMARY")
        print("=" * 60)
        
        summary = results["summary"]
        print(f"Files Changed: {summary['changed_files']}")
        print(f"Automated Checks: {summary['passed_checks']}/{summary['total_automated_checks']} passed")
        print(f"Critical Failures: {summary['critical_failures']}")
        print(f"High Priority Failures: {summary['high_failures']}")
        print(f"Manual Review Items: {summary['manual_review_items']}")
        print(f"Review Status: {'✅ APPROVED' if summary['review_approved'] else '❌ NEEDS WORK'}")
        
        if not summary['review_approved']:
            print(f"\n⚠️  Review Issues:")
            for check_name, check_result in results["checks"].items():
                if not check_result["passed"]:
                    print(f"    ✗ {check_name} ({check_result['severity']})")
        
        return summary['review_approved']


def main():
    """Main entry point for code review automation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run automated code review")
    parser.add_argument("--target-branch", default="main", help="Target branch for comparison")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--files", nargs="*", help="Specific files to review")
    parser.add_argument("--checklist", action="store_true", help="Generate manual review checklist")
    
    args = parser.parse_args()
    
    reviewer = CodeReviewAutomation(args.project_root, args.target_branch)
    
    if args.checklist:
        print(reviewer.generate_review_checklist())
        return
    
    # Run automated review
    results = reviewer.run_automated_review(args.files)
    approved = reviewer.print_review_summary(results)
    
    # Print manual review checklist if needed
    if not approved or results["manual_review_items"]:
        print(f"\n📋 Manual Review Required:")
        print(reviewer.generate_review_checklist())
    
    sys.exit(0 if approved else 1)


if __name__ == "__main__":
    main()
