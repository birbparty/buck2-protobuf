"""
Test helper utilities for ORAS testing.

This module provides common utilities and helpers used across
the ORAS test suite.
"""

import json
import time
import hashlib
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from unittest.mock import Mock, patch


class MockArtifact:
    """Mock artifact for testing."""
    
    def __init__(self, name: str, size: int, content: Optional[bytes] = None):
        self.name = name
        self.size = size
        self.content = content or self._generate_content(size)
        self.digest = f"sha256:{hashlib.sha256(self.content).hexdigest()}"
    
    def _generate_content(self, size: int) -> bytes:
        """Generate mock content of specified size."""
        # Create deterministic content based on name and size
        seed = f"{self.name}-{size}"
        content = seed.encode() * (size // len(seed) + 1)
        return content[:size]
    
    def save_to_file(self, file_path: Path) -> Path:
        """Save mock artifact to a file."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(self.content)
        return file_path


class TestRegistry:
    """Mock registry for testing."""
    
    def __init__(self):
        self.artifacts: Dict[str, MockArtifact] = {}
        self.tags: Dict[str, List[str]] = {}
        self.auth_required = False
        self.valid_credentials = {"user": "test", "password": "test"}
    
    def add_artifact(self, ref: str, artifact: MockArtifact, tags: List[str] = None):
        """Add artifact to mock registry."""
        self.artifacts[ref] = artifact
        repo = ref.split(':')[0]
        self.tags[repo] = tags or ["latest"]
    
    def get_artifact(self, ref: str) -> Optional[MockArtifact]:
        """Get artifact from mock registry."""
        return self.artifacts.get(ref)
    
    def list_tags(self, repo: str) -> List[str]:
        """List tags for repository."""
        return self.tags.get(repo, [])


class PerformanceBenchmark:
    """Performance benchmarking utilities."""
    
    def __init__(self):
        self.measurements = []
        self.start_time = None
    
    def start(self):
        """Start timing."""
        self.start_time = time.time()
    
    def stop(self, label: str = "measurement") -> float:
        """Stop timing and record measurement."""
        if self.start_time is None:
            raise RuntimeError("Must call start() before stop()")
        
        elapsed = time.time() - self.start_time
        self.measurements.append({
            "label": label,
            "elapsed": elapsed,
            "timestamp": time.time()
        })
        self.start_time = None
        return elapsed
    
    def get_statistics(self) -> Dict[str, float]:
        """Get performance statistics."""
        if not self.measurements:
            return {}
        
        times = [m["elapsed"] for m in self.measurements]
        return {
            "count": len(times),
            "total": sum(times),
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times)
        }


class CoverageMeasurement:
    """Test coverage measurement utilities."""
    
    def __init__(self, target_coverage: float = 95.0):
        self.target_coverage = target_coverage
        self.coverage_data = {}
    
    def measure_coverage(self, test_command: List[str]) -> Dict[str, Any]:
        """Measure test coverage."""
        try:
            # Run tests with coverage
            cmd = ["python", "-m", "pytest"] + test_command + [
                "--cov=tools",
                "--cov-report=json",
                "--cov-report=term-missing"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Load coverage data
            coverage_file = Path("coverage.json")
            if coverage_file.exists():
                with open(coverage_file) as f:
                    self.coverage_data = json.load(f)
            
            return {
                "success": result.returncode == 0,
                "coverage_data": self.coverage_data,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "coverage_data": {}
            }
    
    def validate_coverage(self) -> Dict[str, Any]:
        """Validate coverage meets target."""
        if not self.coverage_data:
            return {"valid": False, "reason": "No coverage data available"}
        
        total_coverage = self.coverage_data.get("totals", {}).get("percent_covered", 0)
        
        return {
            "valid": total_coverage >= self.target_coverage,
            "actual_coverage": total_coverage,
            "target_coverage": self.target_coverage,
            "gap": max(0, self.target_coverage - total_coverage)
        }


class NetworkSimulator:
    """Network condition simulation for testing."""
    
    def __init__(self):
        self.conditions = {
            "normal": {"latency": 0, "packet_loss": 0, "bandwidth_limit": None},
            "slow": {"latency": 500, "packet_loss": 1, "bandwidth_limit": "1mbps"},
            "unreliable": {"latency": 200, "packet_loss": 10, "bandwidth_limit": None},
            "offline": {"latency": None, "packet_loss": 100, "bandwidth_limit": None}
        }
    
    def apply_conditions(self, condition: str):
        """Apply network conditions (mock implementation)."""
        if condition not in self.conditions:
            raise ValueError(f"Unknown network condition: {condition}")
        
        # In real implementation, this would use tools like tc (traffic control)
        # or network namespaces to simulate conditions
        settings = self.conditions[condition]
        
        return MockNetworkCondition(settings)


class MockNetworkCondition:
    """Mock network condition context manager."""
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class SecurityTestHelper:
    """Security testing utilities."""
    
    @staticmethod
    def generate_malicious_inputs() -> List[str]:
        """Generate malicious inputs for security testing."""
        return [
            # Path traversal
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            
            # Command injection
            "test; rm -rf /",
            "test$(whoami)",
            "test`cat /etc/passwd`",
            
            # SQL injection patterns (even though we don't use SQL)
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            
            # Script injection
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            
            # Null bytes and special characters
            "test\x00.txt",
            "test\r\n.txt",
            "test\t.txt",
            
            # Long inputs (buffer overflow attempts)
            "A" * 10000,
            "test" + "B" * 1000,
        ]
    
    @staticmethod
    def scan_for_secrets(content: str) -> List[Dict[str, str]]:
        """Scan content for potential secrets."""
        import re
        
        patterns = {
            "password": r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]+)',
            "token": r'(?i)(token|key|secret)\s*[:=]\s*["\']?([^"\'\s]+)',
            "api_key": r'(?i)(api[_-]?key)\s*[:=]\s*["\']?([^"\'\s]+)',
            "github_token": r'ghp_[a-zA-Z0-9]{36}',
            "aws_key": r'AKIA[0-9A-Z]{16}',
            "private_key": r'-----BEGIN [A-Z ]+PRIVATE KEY-----',
        }
        
        findings = []
        for secret_type, pattern in patterns.items():
            matches = re.finditer(pattern, content)
            for match in matches:
                findings.append({
                    "type": secret_type,
                    "match": match.group(),
                    "line": content[:match.start()].count('\n') + 1,
                    "column": match.start() - content.rfind('\n', 0, match.start())
                })
        
        return findings


class TestEnvironment:
    """Test environment management."""
    
    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or Path(tempfile.mkdtemp(prefix="oras-test-"))
        self.cache_dir = self.temp_dir / "cache"
        self.artifacts_dir = self.temp_dir / "artifacts"
        self.logs_dir = self.temp_dir / "logs"
        
        # Create directories
        for directory in [self.cache_dir, self.artifacts_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)
    
    def create_mock_artifact(self, name: str, size: int) -> Path:
        """Create a mock artifact file."""
        artifact = MockArtifact(name, size)
        artifact_path = self.artifacts_dir / f"{name}.bin"
        return artifact.save_to_file(artifact_path)
    
    def cleanup(self):
        """Clean up test environment."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()


class TestDataGenerator:
    """Generate test data for ORAS testing."""
    
    @staticmethod
    def create_test_artifacts() -> Dict[str, Dict[str, Any]]:
        """Create test artifact configurations."""
        return {
            "small_binary": {
                "name": "hello-world",
                "size": 1024,  # 1KB
                "ref": "oras.birb.homes/buck2-protobuf/test/hello-world:latest",
                "type": "binary"
            },
            "medium_binary": {
                "name": "protoc-test",
                "size": 5 * 1024 * 1024,  # 5MB
                "ref": "oras.birb.homes/buck2-protobuf/test/protoc:v24.4-linux-x86_64",
                "type": "binary"
            },
            "large_binary": {
                "name": "large-test",
                "size": 50 * 1024 * 1024,  # 50MB
                "ref": "oras.birb.homes/buck2-protobuf/test/large:latest",
                "type": "binary"
            },
            "plugin_go": {
                "name": "protoc-gen-go",
                "size": 10 * 1024 * 1024,  # 10MB
                "ref": "oras.birb.homes/buck2-protobuf/plugins/protoc-gen-go:v1.34.2-linux-x86_64",
                "type": "plugin"
            },
            "bundle_go": {
                "name": "go-development",
                "size": 25 * 1024 * 1024,  # 25MB
                "ref": "oras.birb.homes/buck2-protobuf/bundles/go-development:latest",
                "type": "bundle"
            }
        }
    
    @staticmethod
    def create_test_platforms() -> List[str]:
        """Create list of test platforms."""
        return [
            "linux-x86_64",
            "linux-aarch64",
            "darwin-x86_64", 
            "darwin-arm64",
            "windows-x86_64"
        ]
    
    @staticmethod
    def create_test_versions() -> Dict[str, List[str]]:
        """Create test version configurations."""
        return {
            "protoc": ["24.4", "25.1", "25.2", "26.0", "26.1"],
            "protoc-gen-go": ["1.34.2", "1.34.1", "1.33.0"],
            "protoc-gen-go-grpc": ["1.5.1", "1.5.0", "1.4.0"],
            "grpcio-tools": ["1.66.2", "1.66.1", "1.65.0"],
            "protoc-gen-ts": ["0.8.7", "0.8.6", "0.8.5"]
        }


class TestReporter:
    """Test result reporting utilities."""
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
    
    def add_result(self, test_name: str, status: str, duration: float, 
                   details: Dict[str, Any] = None):
        """Add test result."""
        self.results.append({
            "test_name": test_name,
            "status": status,
            "duration": duration,
            "timestamp": time.time(),
            "details": details or {}
        })
    
    def generate_report(self, format: str = "json") -> Path:
        """Generate test report."""
        timestamp = int(time.time())
        
        if format == "json":
            report_file = self.output_dir / f"oras_test_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump({
                    "summary": self._generate_summary(),
                    "results": self.results,
                    "generated_at": timestamp
                }, f, indent=2)
        
        elif format == "html":
            report_file = self.output_dir / f"oras_test_report_{timestamp}.html"
            with open(report_file, 'w') as f:
                f.write(self._generate_html_report())
        
        else:
            raise ValueError(f"Unsupported report format: {format}")
        
        return report_file
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["status"] == "passed")
        failed = sum(1 for r in self.results if r["status"] == "failed")
        skipped = sum(1 for r in self.results if r["status"] == "skipped")
        
        total_duration = sum(r["duration"] for r in self.results)
        
        return {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": passed / total if total > 0 else 0,
            "total_duration": total_duration
        }
    
    def _generate_html_report(self) -> str:
        """Generate HTML test report."""
        summary = self._generate_summary()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ORAS Integration Test Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .skipped {{ color: orange; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>ORAS Integration Test Report</h1>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Tests: {summary['total_tests']}</p>
                <p class="passed">Passed: {summary['passed']}</p>
                <p class="failed">Failed: {summary['failed']}</p>
                <p class="skipped">Skipped: {summary['skipped']}</p>
                <p>Success Rate: {summary['success_rate']:.1%}</p>
                <p>Total Duration: {summary['total_duration']:.2f}s</p>
            </div>
            
            <table>
                <tr>
                    <th>Test Name</th>
                    <th>Status</th>
                    <th>Duration</th>
                    <th>Details</th>
                </tr>
        """
        
        for result in self.results:
            status_class = result["status"]
            details = json.dumps(result["details"], indent=2) if result["details"] else ""
            
            html += f"""
                <tr>
                    <td>{result['test_name']}</td>
                    <td class="{status_class}">{result['status']}</td>
                    <td>{result['duration']:.2f}s</td>
                    <td><pre>{details}</pre></td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html


def validate_oras_environment() -> Dict[str, Any]:
    """Validate ORAS testing environment."""
    checks = {}
    
    # Check Python version
    import sys
    python_version = sys.version_info
    checks["python_version"] = {
        "valid": python_version >= (3, 7),
        "actual": f"{python_version.major}.{python_version.minor}.{python_version.micro}",
        "required": "3.7+"
    }
    
    # Check required modules
    required_modules = ["pytest", "requests", "pathlib", "tempfile", "hashlib"]
    checks["modules"] = {}
    
    for module in required_modules:
        try:
            __import__(module)
            checks["modules"][module] = {"available": True}
        except ImportError as e:
            checks["modules"][module] = {"available": False, "error": str(e)}
    
    # Check network connectivity
    try:
        import requests
        response = requests.get("https://oras.birb.homes", timeout=5)
        checks["network_connectivity"] = {
            "available": True,
            "registry_reachable": response.status_code < 500
        }
    except Exception as e:
        checks["network_connectivity"] = {
            "available": False,
            "error": str(e)
        }
    
    # Check disk space
    import shutil
    temp_dir = Path(tempfile.gettempdir())
    free_space_gb = shutil.disk_usage(temp_dir).free / (1024**3)
    
    checks["disk_space"] = {
        "available_gb": free_space_gb,
        "sufficient": free_space_gb > 1.0  # At least 1GB free
    }
    
    # Overall validation
    all_valid = True
    
    # Check each category
    for category_name, category_data in checks.items():
        if isinstance(category_data, dict):
            if "valid" in category_data:
                if not category_data["valid"]:
                    all_valid = False
                    break
            elif "available" in category_data:
                if not category_data["available"]:
                    all_valid = False
                    break
            else:
                # Check sub-items if it's a nested dict
                for item_name, item_data in category_data.items():
                    if isinstance(item_data, dict):
                        if "valid" in item_data and not item_data["valid"]:
                            all_valid = False
                            break
                        elif "available" in item_data and not item_data["available"]:
                            all_valid = False
                            break
    
    checks["overall"] = {"valid": all_valid}
    
    return checks


def setup_test_artifacts(registry_url: str = "oras.birb.homes") -> Dict[str, Any]:
    """Set up test artifacts in registry."""
    # This would be used to publish test artifacts to the registry
    # For now, return configuration for expected test artifacts
    
    artifacts = TestDataGenerator.create_test_artifacts()
    
    # Update registry URLs
    for artifact in artifacts.values():
        if not artifact["ref"].startswith(registry_url):
            artifact["ref"] = artifact["ref"].replace("oras.birb.homes", registry_url)
    
    return {
        "registry": registry_url,
        "artifacts": artifacts,
        "setup_required": True,
        "setup_instructions": [
            f"Publish test artifacts to {registry_url}",
            "Configure authentication if required",
            "Verify artifact accessibility"
        ]
    }
