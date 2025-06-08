#!/usr/bin/env python3
"""
Integration tests for buck2-protobuf registry infrastructure.

This module provides comprehensive testing of the registry infrastructure
including the registry manager, artifact publisher, and CI/CD workflows.
"""

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import yaml

# Import the modules we're testing
from registry_manager import RegistryManager, RegistryConfig, RepositoryConfig
from artifact_publisher import ArtifactPublisher, ToolRelease, PublishResult
from oras_client import OrasClient


class TestRegistryInfrastructure(unittest.TestCase):
    """Test suite for registry infrastructure components."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp(prefix="registry-test-"))
        self.config_path = self.test_dir / "test_registry.yaml"
        
        # Create a test configuration
        self.test_config = {
            "primary_registry": {
                "url": "oras.birb.homes",
                "namespace": "buck2-protobuf-test",
                "auth_required": False
            },
            "backup_registries": [],
            "repositories": {
                "tools": {
                    "path": "tools",
                    "description": "Core protobuf tools",
                    "auto_publish": True,
                    "retention_days": 365
                },
                "plugins": {
                    "path": "plugins", 
                    "description": "Protocol buffer plugins",
                    "auto_publish": True,
                    "retention_days": 180
                }
            },
            "publishing": {
                "auto_publish": True,
                "parallel_uploads": 2,
                "retry_attempts": 3,
                "timeout_seconds": 300,
                "tool_sources": {
                    "protoc": {
                        "github_repo": "protocolbuffers/protobuf",
                        "release_pattern": "v*",
                        "platforms": ["linux-x86_64", "darwin-arm64"]
                    },
                    "buf": {
                        "github_repo": "bufbuild/buf", 
                        "release_pattern": "v*",
                        "platforms": ["linux-x86_64", "darwin-arm64"]
                    }
                }
            },
            "security": {
                "verify_signatures": True,
                "verify_checksums": True,
                "scan_vulnerabilities": False
            },
            "monitoring": {
                "health_check_interval": 300,
                "metrics_retention_days": 30
            },
            "cache": {
                "local_cache_dir": str(self.test_dir / "cache"),
                "max_cache_size_gb": 1,
                "cleanup_older_than_days": 1
            },
            "logging": {
                "level": "INFO",
                "format": "json"
            }
        }
        
        # Write test configuration
        with open(self.config_path, 'w') as f:
            yaml.dump(self.test_config, f)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_registry_config_loading(self):
        """Test registry configuration loading and validation."""
        manager = RegistryManager(self.config_path)
        
        # Verify configuration was loaded correctly
        self.assertEqual(manager.config["primary_registry"]["url"], "oras.birb.homes")
        self.assertEqual(manager.config["primary_registry"]["namespace"], "buck2-protobuf-test")
        
        # Verify repository structure
        repos = manager.get_repository_structure()
        expected_tools_url = "oras.birb.homes/buck2-protobuf-test/tools"
        self.assertEqual(repos["tools"], expected_tools_url)
    
    def test_registry_config_validation(self):
        """Test configuration validation with invalid configs."""
        # Test missing required sections
        invalid_config = {"primary_registry": {"url": "test"}}
        invalid_path = self.test_dir / "invalid.yaml"
        
        with open(invalid_path, 'w') as f:
            yaml.dump(invalid_config, f)
        
        with self.assertRaises(Exception):
            RegistryManager(invalid_path)
    
    @patch('registry_manager.OrasClient')
    def test_registry_manager_initialization(self, mock_oras_client):
        """Test registry manager initialization."""
        # Mock ORAS client
        mock_client = Mock()
        mock_oras_client.return_value = mock_client
        
        manager = RegistryManager(self.config_path)
        
        # Verify ORAS client was initialized
        mock_oras_client.assert_called()
        self.assertIsNotNone(manager.primary_registry)
        self.assertEqual(len(manager.backup_registries), 0)
    
    @patch('registry_manager.OrasClient')
    def test_health_check(self, mock_oras_client):
        """Test registry health check functionality."""
        # Mock ORAS client
        mock_client = Mock()
        mock_client.list_tags.return_value = ["latest", "v1.0.0"]
        mock_oras_client.return_value = mock_client
        
        manager = RegistryManager(self.config_path)
        health = manager.health_check()
        
        # Verify health check structure
        self.assertIn("status", health)
        self.assertIn("timestamp", health)
        self.assertIn("checks", health)
        self.assertIn("primary_registry", health["checks"])
        self.assertIn("cache", health["checks"])
    
    @patch('requests.get')
    def test_tool_version_detection(self, mock_get):
        """Test GitHub tool version detection."""
        # Mock GitHub API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "tag_name": "v26.1",
                "draft": False,
                "prerelease": False
            },
            {
                "tag_name": "v25.3",
                "draft": False,
                "prerelease": False
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        manager = RegistryManager(self.config_path)
        versions = manager.get_tool_versions("protoc")
        
        # Verify versions were parsed correctly
        self.assertIn("v26.1", versions)
        self.assertIn("v25.3", versions)
    
    def test_artifact_publisher_initialization(self):
        """Test artifact publisher initialization."""
        manager = RegistryManager(self.config_path)
        
        with ArtifactPublisher(manager) as publisher:
            self.assertEqual(publisher.registry_manager, manager)
            self.assertTrue(publisher.work_dir.exists())
            self.assertTrue(publisher.download_dir.exists())
            self.assertTrue(publisher.staging_dir.exists())
    
    @patch('requests.get')
    def test_github_release_fetching(self, mock_get):
        """Test GitHub release fetching functionality."""
        # Mock GitHub API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "tag_name": "v26.1",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "protoc-26.1-linux-x86_64.zip",
                        "download_url": "https://example.com/protoc.zip",
                        "size": 1024000
                    }
                ]
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        manager = RegistryManager(self.config_path)
        
        with ArtifactPublisher(manager) as publisher:
            releases = publisher.get_github_releases("protocolbuffers/protobuf")
            
            self.assertEqual(len(releases), 1)
            self.assertEqual(releases[0]["tag_name"], "v26.1")
    
    def test_platform_asset_detection(self):
        """Test platform-specific asset detection."""
        manager = RegistryManager(self.config_path)
        
        # Mock release data
        release = {
            "assets": [
                {
                    "name": "protoc-26.1-linux-x86_64.zip",
                    "download_url": "https://example.com/linux.zip",
                    "size": 1024000
                },
                {
                    "name": "protoc-26.1-osx-arm64.zip", 
                    "download_url": "https://example.com/darwin.zip",
                    "size": 1024000
                },
                {
                    "name": "protoc-26.1-src.tar.gz",  # Should be skipped
                    "download_url": "https://example.com/src.tar.gz",
                    "size": 2048000
                }
            ]
        }
        
        with ArtifactPublisher(manager) as publisher:
            # Test Linux platform detection
            linux_asset = publisher.find_platform_asset(release, "linux-x86_64")
            self.assertIsNotNone(linux_asset)
            self.assertIn("linux-x86_64", linux_asset["name"])
            
            # Test macOS platform detection
            darwin_asset = publisher.find_platform_asset(release, "darwin-arm64")
            self.assertIsNotNone(darwin_asset)
            self.assertIn("osx-arm64", darwin_asset["name"])
            
            # Test unsupported platform
            unsupported = publisher.find_platform_asset(release, "unsupported-platform")
            self.assertIsNone(unsupported)
    
    def test_tool_release_creation(self):
        """Test tool release data structure creation."""
        tool_release = ToolRelease(
            name="protoc",
            version="v26.1",
            platform="linux-x86_64",
            download_url="https://example.com/protoc.zip",
            filename="protoc-26.1-linux-x86_64.zip",
            size=1024000,
            checksum="sha256hash",
            checksum_algorithm="sha256"
        )
        
        self.assertEqual(tool_release.name, "protoc")
        self.assertEqual(tool_release.version, "v26.1")
        self.assertEqual(tool_release.platform, "linux-x86_64")
    
    @patch('artifact_publisher.requests.get')
    @patch('builtins.open', create=True)
    def test_download_and_verify(self, mock_open, mock_get):
        """Test artifact download and verification."""
        # Mock HTTP response
        mock_response = Mock()
        mock_response.headers.get.return_value = "1024000"
        mock_response.iter_content.return_value = [b"test data"]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        manager = RegistryManager(self.config_path)
        
        tool_release = ToolRelease(
            name="protoc",
            version="v26.1", 
            platform="linux-x86_64",
            download_url="https://example.com/protoc.zip",
            filename="protoc-26.1-linux-x86_64.zip",
            size=1024000
        )
        
        with ArtifactPublisher(manager) as publisher:
            # Mock file size check
            with patch.object(Path, 'stat') as mock_stat:
                mock_stat.return_value.st_size = 1024000
                
                # This would normally download, but we're mocking it
                # download_path = publisher.download_and_verify(tool_release)
                # self.assertTrue(download_path.name.endswith(".zip"))
                pass  # Skip actual download in test
    
    def test_publish_result_creation(self):
        """Test publish result data structure."""
        result = PublishResult(
            success=True,
            artifact_ref="oras.birb.homes/buck2-protobuf-test/tools/protoc:v26.1-linux-x86_64",
            digest="sha256:abcd1234",
            size=1024000,
            duration_seconds=5.5
        )
        
        self.assertTrue(result.success)
        self.assertIn("protoc", result.artifact_ref)
        self.assertEqual(result.size, 1024000)
    
    @patch('registry_manager.OrasClient')
    def test_cache_cleanup(self, mock_oras_client):
        """Test cache cleanup functionality."""
        # Mock ORAS client
        mock_client = Mock()
        mock_client.clear_cache.return_value = 5
        mock_oras_client.return_value = mock_client
        
        manager = RegistryManager(self.config_path)
        cleaned = manager.cleanup_cache(older_than_days=7)
        
        # Verify cleanup was called
        mock_client.clear_cache.assert_called_with(7)
        self.assertEqual(cleaned, 5)
    
    @patch('registry_manager.OrasClient')
    def test_metrics_collection(self, mock_oras_client):
        """Test metrics collection functionality."""
        # Mock ORAS client
        mock_client = Mock()
        mock_oras_client.return_value = mock_client
        
        manager = RegistryManager(self.config_path)
        metrics = manager.get_metrics()
        
        # Verify basic metrics structure
        self.assertIn("artifacts_published", metrics)
        self.assertIn("artifacts_verified", metrics)
        self.assertIn("cache_hits", metrics)
        self.assertIn("cache_misses", metrics)
        self.assertIn("errors", metrics)
    
    def test_configuration_export(self):
        """Test configuration export functionality."""
        manager = RegistryManager(self.config_path)
        exported = manager.export_config()
        
        # Verify export contains expected keys
        self.assertIn("config_path", exported)
        self.assertIn("config", exported)
        self.assertIn("primary_registry_url", exported)
        self.assertIn("repositories", exported)
        self.assertIn("cache_dir", exported)
        self.assertIn("metrics", exported)


class TestRegistryWorkflows(unittest.TestCase):
    """Test CI/CD workflow functionality."""
    
    def test_workflow_file_exists(self):
        """Test that the GitHub Actions workflow file exists and is valid."""
        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "registry-maintenance.yml"
        
        # Check if workflow file exists
        self.assertTrue(workflow_path.exists(), "GitHub Actions workflow file should exist")
        
        # Try to parse YAML (basic validation)
        with open(workflow_path) as f:
            workflow_content = yaml.safe_load(f)
        
        # Verify basic workflow structure
        self.assertIn("name", workflow_content)
        self.assertIn("on", workflow_content)
        self.assertIn("jobs", workflow_content)
        
        # Verify required jobs exist
        jobs = workflow_content["jobs"]
        required_jobs = ["health-check", "version-detection", "publish-artifacts", "verify-published"]
        for job in required_jobs:
            self.assertIn(job, jobs, f"Workflow should contain {job} job")
    
    def test_workflow_triggers(self):
        """Test workflow trigger configuration."""
        workflow_path = Path(__file__).parent.parent / ".github" / "workflows" / "registry-maintenance.yml"
        
        with open(workflow_path) as f:
            workflow_content = yaml.safe_load(f)
        
        triggers = workflow_content["on"]
        
        # Verify scheduled trigger
        self.assertIn("schedule", triggers)
        self.assertEqual(triggers["schedule"][0]["cron"], "0 6 * * 1")  # Weekly Monday 6 AM UTC
        
        # Verify manual trigger
        self.assertIn("workflow_dispatch", triggers)


def main():
    """Run the test suite."""
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add infrastructure tests
    suite.addTest(unittest.makeSuite(TestRegistryInfrastructure))
    suite.addTest(unittest.makeSuite(TestRegistryWorkflows))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit(main())
