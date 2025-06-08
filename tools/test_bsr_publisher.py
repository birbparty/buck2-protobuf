#!/usr/bin/env python3
"""
Test suite for BSR Publisher with multi-registry support.

This module tests the BSR publishing workflows including semantic versioning,
multi-registry atomic publishing, team notifications, and governance.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import time

# Import the modules to test
from bsr_publisher import BSRPublisher, PublishResult
from bsr_version_manager import BSRVersionManager, VersionInfo, VersionIncrement, SchemaChange, ChangeType


class TestBSRPublisher(unittest.TestCase):
    """Test cases for BSR Publisher functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_repositories = {
            "primary": "buf.build/testorg/schemas",
            "backup": "oras.birb.homes/testorg/schemas"
        }
        
        # Create mock publisher
        self.publisher = BSRPublisher(
            repositories=self.test_repositories,
            version_strategy="semantic",
            breaking_change_policy="require_approval",
            notify_teams=["@test-team"],
            cache_dir=self.temp_dir,
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_registry_clients(self):
        """Test registry client initialization."""
        publisher = BSRPublisher(
            repositories={
                "bsr": "buf.build/test/repo",
                "oras": "oras.birb.homes/test/repo"
            },
            verbose=True
        )
        
        # Should have attempted to initialize both clients
        # (They may fail without actual services, but should try)
        self.assertEqual(len(publisher.repositories), 2)
    
    @patch('tools.bsr_publisher.subprocess.run')
    def test_extract_proto_files(self, mock_run):
        """Test proto file extraction from Buck2 target."""
        # Mock buck2 query response
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = json.dumps([
            "api/user.proto",
            "api/types.proto",
            "non_proto.txt"
        ])
        
        # Create test proto files
        test_dir = Path(self.temp_dir)
        api_dir = test_dir / "api"
        api_dir.mkdir()
        
        user_proto = api_dir / "user.proto"
        types_proto = api_dir / "types.proto"
        user_proto.write_text("syntax = \"proto3\"; message User {}")
        types_proto.write_text("syntax = \"proto3\"; message Type {}")
        
        # Change working directory for test
        import os
        old_cwd = os.getcwd()
        os.chdir(test_dir)
        
        try:
            proto_files = self.publisher._extract_proto_files("//api:schemas")
            
            # Should extract only .proto files that exist
            self.assertEqual(len(proto_files), 2)
            self.assertTrue(any(f.name == "user.proto" for f in proto_files))
            self.assertTrue(any(f.name == "types.proto" for f in proto_files))
        finally:
            os.chdir(old_cwd)
    
    def test_check_approval_requirements_no_breaking(self):
        """Test approval requirements with no breaking changes."""
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.FEATURE,
                    severity="minor",
                    description="Added new field",
                    file_path="user.proto"
                )
            ],
            change_summary="1 new feature",
            created_at=time.time()
        )
        
        result = self.publisher._check_approval_requirements(version_info)
        
        self.assertFalse(result.approval_required)
        self.assertTrue(result.approved)
        self.assertIn("No breaking changes", result.reason)
    
    def test_check_approval_requirements_breaking_blocked(self):
        """Test approval requirements with breaking changes blocked."""
        publisher = BSRPublisher(
            repositories=self.test_repositories,
            breaking_change_policy="block",
            verbose=True
        )
        
        version_info = VersionInfo(
            version="v2.0.0",
            increment_type=VersionIncrement.MAJOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.BREAKING,
                    severity="major",
                    description="Removed field",
                    file_path="user.proto"
                )
            ],
            change_summary="1 breaking change",
            created_at=time.time()
        )
        
        result = publisher._check_approval_requirements(version_info)
        
        self.assertTrue(result.approval_required)
        self.assertFalse(result.approved)
        self.assertIn("blocked by policy", result.reason)
    
    def test_check_approval_requirements_breaking_allowed(self):
        """Test approval requirements with breaking changes allowed."""
        publisher = BSRPublisher(
            repositories=self.test_repositories,
            breaking_change_policy="allow",
            verbose=True
        )
        
        version_info = VersionInfo(
            version="v2.0.0",
            increment_type=VersionIncrement.MAJOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.BREAKING,
                    severity="major",
                    description="Removed field",
                    file_path="user.proto"
                )
            ],
            change_summary="1 breaking change",
            created_at=time.time()
        )
        
        result = publisher._check_approval_requirements(version_info)
        
        self.assertFalse(result.approval_required)
        self.assertTrue(result.approved)
        self.assertIn("allowed by policy", result.reason)
    
    @patch('tools.bsr_publisher.BSRVersionManager')
    def test_validate_pre_publish_success(self, mock_version_manager):
        """Test successful pre-publish validation."""
        # Mock version manager validation
        mock_vm = mock_version_manager.return_value
        mock_vm.validate_version_consistency.return_value = {
            "primary": True,
            "backup": True
        }
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._validate_pre_publish(version_info)
        
        self.assertTrue(result.success)
        self.assertIsNone(result.error)
    
    @patch('tools.bsr_publisher.BSRVersionManager')
    def test_validate_pre_publish_version_inconsistency(self, mock_version_manager):
        """Test pre-publish validation with version inconsistency."""
        # Mock version manager validation
        mock_vm = mock_version_manager.return_value
        mock_vm.validate_version_consistency.return_value = {
            "primary": True,
            "backup": False  # Inconsistent
        }
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._validate_pre_publish(version_info)
        
        self.assertFalse(result.success)
        self.assertIn("Version inconsistency", result.error)
    
    def test_publish_to_single_registry_unknown_type(self):
        """Test publishing to unknown registry type."""
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        # Mock unknown client
        self.publisher.registry_clients["unknown"] = Mock()
        
        result = self.publisher._publish_to_single_registry(
            "unknown",
            "unknown.com/test/repo",
            version_info,
            [],
            300
        )
        
        # Should handle unknown registry type gracefully
        self.assertIsInstance(result, bool)
    
    @patch('tools.bsr_publisher.subprocess.run')
    def test_publish_to_bsr_success(self, mock_run):
        """Test successful BSR publishing."""
        # Mock successful buf push
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Successfully pushed"
        
        # Create mock BSR client
        mock_client = Mock()
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.FEATURE,
                    severity="minor",
                    description="Test change",
                    file_path="*"
                )
            ],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._publish_to_bsr(
            mock_client,
            "buf.build/test/repo",
            version_info,
            [],
            300
        )
        
        self.assertTrue(result)
        mock_run.assert_called_once()
    
    @patch('tools.bsr_publisher.subprocess.run')
    def test_publish_to_bsr_failure(self, mock_run):
        """Test BSR publishing failure."""
        # Mock failed buf push
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Push failed"
        
        mock_client = Mock()
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._publish_to_bsr(
            mock_client,
            "buf.build/test/repo",
            version_info,
            [],
            300
        )
        
        self.assertFalse(result)
    
    def test_publish_to_oras_with_oras_client(self):
        """Test ORAS publishing with OrasClient."""
        # Mock ORAS client
        mock_client = Mock()
        mock_client.push.return_value = True
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.FEATURE,
                    severity="minor",
                    description="Test change",
                    file_path="*"
                )
            ],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._publish_to_oras(
            mock_client,
            "oras.birb.homes/test/repo",
            version_info,
            [],
            300
        )
        
        self.assertTrue(result)
        mock_client.push.assert_called_once()
    
    def test_publish_to_oras_with_artifact_publisher(self):
        """Test ORAS publishing with ArtifactPublisher."""
        # Mock artifact publisher
        mock_client = Mock()
        mock_client.publish_directory.return_value = True
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[
                SchemaChange(
                    change_type=ChangeType.FEATURE,
                    severity="minor",
                    description="Test change",
                    file_path="*"
                )
            ],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._publish_to_oras(
            mock_client,
            "oras.birb.homes/test/repo",
            version_info,
            [],
            300
        )
        
        self.assertTrue(result)
        mock_client.publish_directory.assert_called_once()
    
    def test_rollback_publications(self):
        """Test rollback functionality."""
        # Mock clients with rollback capability
        mock_client1 = Mock()
        mock_client1.delete_version.return_value = True
        
        mock_client2 = Mock()
        mock_client2.delete_version.return_value = False
        
        self.publisher.registry_clients = {
            "registry1": mock_client1,
            "registry2": mock_client2
        }
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        result = self.publisher._rollback_publications(
            ["registry1", "registry2"],
            version_info
        )
        
        # Should return False because registry2 rollback failed
        self.assertFalse(result)
        mock_client1.delete_version.assert_called_once()
        mock_client2.delete_version.assert_called_once()
    
    @patch('tools.bsr_publisher.BSRTeamManager')
    def test_send_notifications_success(self, mock_team_manager):
        """Test successful notification sending."""
        # Mock team manager
        mock_tm = mock_team_manager.return_value
        mock_tm.get_team_info.return_value = {
            "members": {
                "alice": {"email": "alice@test.com"},
                "bob": {"email": "bob@test.com"}
            }
        }
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test changes",
            created_at=time.time()
        )
        
        publish_result = PublishResult(
            success=True,
            version="v1.1.0",
            repositories={"primary": True}
        )
        
        # Mock email sending
        with patch.object(self.publisher, '_send_email', return_value=True):
            result = self.publisher._send_notifications(version_info, publish_result)
        
        self.assertTrue(result)
    
    @patch('tools.bsr_publisher.BSRTeamManager')
    def test_send_notifications_no_team_info(self, mock_team_manager):
        """Test notification sending with no team info."""
        # Mock team manager returning no info
        mock_tm = mock_team_manager.return_value
        mock_tm.get_team_info.return_value = None
        
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        publish_result = PublishResult(
            success=True,
            version="v1.1.0",
            repositories={"primary": True}
        )
        
        result = self.publisher._send_notifications(version_info, publish_result)
        
        # Should return False because team info not found
        self.assertFalse(result)
    
    def test_log_publish_audit(self):
        """Test audit logging functionality."""
        version_info = VersionInfo(
            version="v1.1.0",
            increment_type=VersionIncrement.MINOR,
            base_version="v1.0.0",
            changes=[],
            change_summary="test",
            created_at=time.time()
        )
        
        publish_result = PublishResult(
            success=True,
            version="v1.1.0",
            repositories={"primary": True},
            publish_time=1.5
        )
        
        # Should not raise exception
        self.publisher._log_publish_audit(version_info, publish_result)
        
        # Check that audit file was created
        audit_files = list(self.publisher.cache_dir.glob("audit_*.json"))
        self.assertGreater(len(audit_files), 0)
        
        # Verify audit file content
        with open(audit_files[0]) as f:
            audit_data = json.load(f)
        
        self.assertEqual(audit_data["version"], "v1.1.0")
        self.assertTrue(audit_data["success"])
        self.assertEqual(audit_data["publish_time"], 1.5)
    
    @patch('tools.bsr_publisher.subprocess.run')
    @patch.object(BSRPublisher, '_extract_proto_files')
    @patch.object(BSRPublisher, '_validate_pre_publish')
    @patch.object(BSRPublisher, '_publish_to_registries')
    def test_publish_schemas_full_workflow(self, mock_publish, mock_validate, mock_extract, mock_run):
        """Test complete schema publishing workflow."""
        # Mock proto file extraction
        mock_extract.return_value = [Path("test.proto")]
        
        # Mock validation
        mock_validation_result = Mock()
        mock_validation_result.success = True
        mock_validation_result.warnings = []
        mock_validate.return_value = mock_validation_result
        
        # Mock successful publishing
        mock_publish.return_value = PublishResult(
            success=True,
            version="v1.1.0",
            repositories={"primary": True, "backup": True}
        )
        
        # Mock Buck2 build
        mock_run.return_value.returncode = 0
        
        # Mock version manager
        with patch.object(self.publisher.version_manager, 'create_version_info') as mock_create_version:
            mock_create_version.return_value = VersionInfo(
                version="v1.1.0",
                increment_type=VersionIncrement.MINOR,
                base_version="v1.0.0",
                changes=[],
                change_summary="test",
                created_at=time.time()
            )
            
            result = self.publisher.publish_schemas(
                proto_target="//api:schemas",
                require_review=False,
                tags=["latest"],
                timeout=300
            )
        
        self.assertTrue(result.success)
        self.assertEqual(result.version, "v1.1.0")
        self.assertGreater(result.publish_time, 0)


class TestBSRPublisherIntegration(unittest.TestCase):
    """Integration tests for BSR Publisher."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Create test proto files
        self.proto_dir = Path(self.temp_dir) / "protos"
        self.proto_dir.mkdir()
        
        # Create sample proto files
        user_proto = self.proto_dir / "user.proto"
        user_proto.write_text("""
syntax = "proto3";

package api.user.v1;

message User {
  string id = 1;
  string name = 2;
  string email = 3;
}
""")
        
        types_proto = self.proto_dir / "types.proto"
        types_proto.write_text("""
syntax = "proto3";

package api.types.v1;

message Timestamp {
  int64 seconds = 1;
  int32 nanos = 2;
}
""")
    
    def tearDown(self):
        """Clean up integration test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_version_manager_integration(self):
        """Test integration with version manager."""
        version_manager = BSRVersionManager(verbose=True)
        
        proto_files = [
            self.proto_dir / "user.proto",
            self.proto_dir / "types.proto"
        ]
        
        version_info = version_manager.create_version_info(
            proto_files=proto_files,
            repositories={"test": "buf.build/test/repo"}
        )
        
        self.assertIsNotNone(version_info)
        self.assertIsNotNone(version_info.version)
        self.assertGreater(len(version_info.changes), 0)
    
    def test_multi_registry_configuration(self):
        """Test multi-registry publisher configuration."""
        repositories = {
            "primary": "buf.build/test/schemas",
            "backup": "oras.birb.homes/test/schemas",
            "mirror": "registry.test.com/test/schemas"
        }
        
        publisher = BSRPublisher(
            repositories=repositories,
            version_strategy="semantic",
            breaking_change_policy="require_approval",
            notify_teams=["@test-team"],
            verbose=True
        )
        
        self.assertEqual(len(publisher.repositories), 3)
        self.assertEqual(publisher.version_strategy, "semantic")
        self.assertEqual(publisher.breaking_change_policy, "require_approval")
        self.assertIn("@test-team", publisher.notify_teams)


def run_publisher_tests():
    """Run all BSR publisher tests."""
    test_suite = unittest.TestSuite()
    
    # Add unit tests
    test_suite.addTest(unittest.makeSuite(TestBSRPublisher))
    
    # Add integration tests
    test_suite.addTest(unittest.makeSuite(TestBSRPublisherIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_publisher_tests()
    exit(0 if success else 1)
