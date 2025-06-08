"""
Pytest configuration and fixtures for ORAS testing.

This module provides shared fixtures, configuration, and utilities
for the comprehensive ORAS test suite.
"""

import os
import pytest
import tempfile
import time
from pathlib import Path
from typing import Dict, Any, Optional, Generator
from unittest.mock import Mock, patch

# Import ORAS components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools"))

from oras_client import OrasClient, OrasClientError
from oras_plugins import PluginOrasDistributor
from oras_protoc import ProtocOrasDistributor
from registry_manager import RegistryManager


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--real-registry",
        action="store_true",
        default=False,
        help="Run tests against real oras.birb.homes registry"
    )
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run performance benchmarks"
    )
    parser.addoption(
        "--platform",
        action="store",
        default=None,
        help="Test specific platform (linux-x86_64, darwin-arm64, etc.)"
    )
    parser.addoption(
        "--skip-slow",
        action="store_true",
        default=False,
        help="Skip slow tests (>30 seconds)"
    )


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "real_registry: marks tests as requiring real registry access"
    )
    config.addinivalue_line(
        "markers", "benchmark: marks tests as performance benchmarks"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (>30 seconds)"
    )
    config.addinivalue_line(
        "markers", "failure_scenario: marks tests as failure scenario testing"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security validation"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command line options."""
    if config.getoption("--real-registry"):
        # Don't skip real registry tests
        pass
    else:
        # Skip real registry tests by default
        skip_real = pytest.mark.skip(reason="need --real-registry option to run")
        for item in items:
            if "real_registry" in item.keywords:
                item.add_marker(skip_real)
    
    if config.getoption("--skip-slow"):
        skip_slow = pytest.mark.skip(reason="--skip-slow option provided")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    
    if not config.getoption("--benchmark"):
        skip_bench = pytest.mark.skip(reason="need --benchmark option to run")
        for item in items:
            if "benchmark" in item.keywords:
                item.add_marker(skip_bench)


@pytest.fixture(scope="session")
def test_registry_url():
    """Registry URL for testing."""
    return "oras.birb.homes"


@pytest.fixture(scope="session")
def test_namespace():
    """Test namespace for artifacts."""
    return "buck2-protobuf/test"


@pytest.fixture
def temp_cache_dir() -> Generator[Path, None, None]:
    """Temporary cache directory for testing."""
    with tempfile.TemporaryDirectory(prefix="oras-test-cache-") as temp_dir:
        cache_dir = Path(temp_dir)
        yield cache_dir


@pytest.fixture
def mock_oras_client():
    """Mock ORAS client for unit tests."""
    with patch('oras_client.OrasClient') as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        
        # Setup default mock behavior
        mock_client.pull.return_value = Path("/mock/artifact/path")
        mock_client.list_tags.return_value = ["latest", "v1.0.0"]
        mock_client.get_artifact_info.return_value = {
            "digest": "sha256:mockdigest123",
            "size": 1024000,
            "platform": "linux-x86_64"
        }
        mock_client.verify_artifact.return_value = True
        mock_client.clear_cache.return_value = 5
        
        yield mock_client


@pytest.fixture
def real_oras_client(temp_cache_dir, test_registry_url):
    """Real ORAS client for integration tests."""
    client = OrasClient(
        registry=test_registry_url,
        cache_dir=temp_cache_dir,
        verbose=False
    )
    yield client


@pytest.fixture
def plugin_distributor(temp_cache_dir, test_registry_url):
    """Plugin distributor for testing."""
    distributor = PluginOrasDistributor(
        registry=test_registry_url,
        cache_dir=str(temp_cache_dir),
        verbose=False
    )
    yield distributor


@pytest.fixture
def protoc_distributor(temp_cache_dir, test_registry_url):
    """Protoc distributor for testing."""
    distributor = ProtocOrasDistributor(
        registry=test_registry_url,
        cache_dir=str(temp_cache_dir),
        verbose=False
    )
    yield distributor


@pytest.fixture
def registry_manager(temp_cache_dir):
    """Registry manager for testing."""
    # Create test configuration
    config_data = {
        "primary_registry": {
            "url": "oras.birb.homes",
            "namespace": "buck2-protobuf/test",
            "auth_required": False
        },
        "backup_registries": [],
        "repositories": {
            "tools": {"path": "tools", "auto_publish": True},
            "plugins": {"path": "plugins", "auto_publish": True}
        },
        "cache": {
            "local_cache_dir": str(temp_cache_dir),
            "max_cache_size_gb": 1
        }
    }
    
    config_file = temp_cache_dir / "test_registry.yaml"
    import yaml
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    
    manager = RegistryManager(config_file)
    yield manager


@pytest.fixture
def performance_timer():
    """Timer for performance measurement."""
    class Timer:
        def __init__(self):
            self.start_time = None
            self.end_time = None
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            return self.elapsed
        
        @property
        def elapsed(self):
            if self.start_time is None:
                return 0
            end = self.end_time or time.time()
            return end - self.start_time
    
    return Timer()


@pytest.fixture
def failure_simulator():
    """Failure simulation utilities."""
    class FailureSimulator:
        def __init__(self):
            self.patches = []
        
        def simulate_network_timeout(self, target_module="requests"):
            """Simulate network timeout."""
            import requests
            patch_obj = patch(f'{target_module}.get', side_effect=requests.Timeout("Network timeout"))
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def simulate_registry_unavailable(self, oras_client):
            """Simulate registry unavailable."""
            oras_client.pull.side_effect = OrasClientError("Registry unavailable")
            oras_client.list_tags.side_effect = OrasClientError("Registry unavailable")
        
        def simulate_authentication_failure(self, oras_client):
            """Simulate authentication failure."""
            oras_client.pull.side_effect = OrasClientError("Authentication failed")
        
        def simulate_disk_full(self, target_path):
            """Simulate disk full error."""
            def mock_write(*args, **kwargs):
                raise OSError("No space left on device")
            
            patch_obj = patch('builtins.open', side_effect=mock_write)
            self.patches.append(patch_obj)
            return patch_obj.start()
        
        def cleanup(self):
            """Cleanup all patches."""
            for patch_obj in self.patches:
                try:
                    patch_obj.stop()
                except RuntimeError:
                    pass  # Already stopped
            self.patches.clear()
    
    simulator = FailureSimulator()
    yield simulator
    simulator.cleanup()


@pytest.fixture
def test_artifacts():
    """Test artifact configurations."""
    return {
        "small_binary": {
            "name": "hello-world",
            "size": 1024,  # 1KB
            "ref": "oras.birb.homes/buck2-protobuf/test/hello-world:latest"
        },
        "medium_binary": {
            "name": "protoc-test",
            "size": 5 * 1024 * 1024,  # 5MB
            "ref": "oras.birb.homes/buck2-protobuf/test/protoc:v24.4-linux-x86_64"
        },
        "large_binary": {
            "name": "large-test",
            "size": 50 * 1024 * 1024,  # 50MB
            "ref": "oras.birb.homes/buck2-protobuf/test/large:latest"
        }
    }


@pytest.fixture
def performance_baselines():
    """Performance baseline expectations."""
    from . import PERFORMANCE_TARGETS
    return PERFORMANCE_TARGETS.copy()


@pytest.fixture
def coverage_validator():
    """Coverage validation utilities."""
    class CoverageValidator:
        def __init__(self):
            self.target_coverage = 95.0
        
        def validate_coverage(self, coverage_data: Dict[str, Any]) -> bool:
            """Validate that coverage meets target."""
            total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
            return total_coverage >= self.target_coverage
        
        def get_uncovered_lines(self, coverage_data: Dict[str, Any]) -> Dict[str, list]:
            """Get uncovered lines by file."""
            uncovered = {}
            for filename, file_data in coverage_data.get("files", {}).items():
                missing_lines = file_data.get("missing_lines", [])
                if missing_lines:
                    uncovered[filename] = missing_lines
            return uncovered
    
    return CoverageValidator()


@pytest.fixture
def security_validator():
    """Security validation utilities."""
    class SecurityValidator:
        def validate_digest(self, content: bytes, expected_digest: str) -> bool:
            """Validate content matches expected digest."""
            import hashlib
            actual_digest = f"sha256:{hashlib.sha256(content).hexdigest()}"
            return actual_digest == expected_digest
        
        def validate_permissions(self, file_path: Path) -> bool:
            """Validate file has secure permissions."""
            import stat
            mode = file_path.stat().st_mode
            # Check that file is not world-writable
            return not (mode & stat.S_IWOTH)
        
        def scan_for_secrets(self, content: str) -> list:
            """Scan content for potential secrets."""
            import re
            patterns = [
                r'(?i)(password|passwd|pwd)\s*[:=]\s*["\']?([^"\'\s]+)',
                r'(?i)(token|key|secret)\s*[:=]\s*["\']?([^"\'\s]+)',
                r'(?i)(api[_-]?key)\s*[:=]\s*["\']?([^"\'\s]+)',
            ]
            
            findings = []
            for pattern in patterns:
                matches = re.findall(pattern, content)
                findings.extend(matches)
            
            return findings
    
    return SecurityValidator()


# Platform detection for cross-platform testing
@pytest.fixture
def current_platform():
    """Current platform string."""
    import platform
    
    system = platform.system().lower()
    machine = platform.machine().lower()
    
    # Normalize platform strings
    if system == "darwin":
        if machine in ("arm64", "aarch64"):
            return "darwin-arm64"
        else:
            return "darwin-x86_64"
    elif system == "linux":
        if machine in ("arm64", "aarch64"):
            return "linux-aarch64"
        else:
            return "linux-x86_64"
    elif system == "windows":
        return "windows-x86_64"
    else:
        return f"{system}-{machine}"


@pytest.fixture(scope="session")
def supported_platforms():
    """List of supported platforms for testing."""
    return [
        "linux-x86_64",
        "linux-aarch64", 
        "darwin-x86_64",
        "darwin-arm64",
        "windows-x86_64"
    ]
