#!/usr/bin/env python3
"""
Tests for Private BSR Repository Authentication System.

This test suite validates the private BSR authentication functionality including
team-based access control, repository configuration, and authentication workflows.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

try:
    from .bsr_private_auth import (
        PrivateBSRAuthenticator, 
        TeamPermission, 
        PrivateRepositoryConfig,
        BSRAuthenticationError
    )
    from .bsr_auth import BSRCredentials
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(str(Path(__file__).parent))
    from bsr_private_auth import (
        PrivateBSRAuthenticator, 
        TeamPermission, 
        PrivateRepositoryConfig,
        BSRAuthenticationError
    )
    from bsr_auth import BSRCredentials


class TestTeamPermission(unittest.TestCase):
    """Test cases for TeamPermission dataclass."""
    
    def test_valid_team_permission_creation(self):
        """Test creating valid team permissions."""
        perm = TeamPermission(team_name="platform-team", access_level="read")
        
        self.assertEqual(perm.team_name, "platform-team")
        self.assertEqual(perm.access_level, "read")
        self.assertIsNotNone(perm.granted_at)
    
    def test_invalid_access_level(self):
        """Test that invalid access levels raise ValueError."""
        with self.assertRaises(ValueError):
            TeamPermission(team_name="team", access_level="invalid")
    
    def test_all_valid_access_levels(self):
        """Test all valid access levels."""
        for level in ["read", "write", "admin"]:
            perm = TeamPermission(team_name="team", access_level=level)
            self.assertEqual(perm.access_level, level)


class TestPrivateRepositoryConfig(unittest.TestCase):
    """Test cases for PrivateRepositoryConfig."""
    
    def test_basic_config_creation(self):
        """Test creating a basic repository configuration."""
        config = PrivateRepositoryConfig(
            repository="buf.build/myorg/private-schemas"
        )
        
        self.assertEqual(config.repository, "buf.build/myorg/private-schemas")
        self.assertEqual(config.auth_method, "auto")
        self.assertEqual(len(config.teams), 0)
        self.assertIsNotNone(config.created_at)
    
    def test_config_with_string_teams(self):
        """Test configuration with string team names."""
        config = PrivateRepositoryConfig(
            repository="buf.build/myorg/private-schemas",
            teams=["platform-team", "backend-team"]
        )
        
        self.assertEqual(len(config.teams), 2)
        self.assertIsInstance(config.teams[0], TeamPermission)
        self.assertEqual(config.teams[0].team_name, "platform-team")
        self.assertEqual(config.teams[0].access_level, "read")  # Default
    
    def test_config_with_team_permission_objects(self):
        """Test configuration with TeamPermission objects."""
        team_perm = TeamPermission(team_name="admin-team", access_level="admin")
        config = PrivateRepositoryConfig(
            repository="buf.build/myorg/private-schemas",
            teams=[team_perm]
        )
        
        self.assertEqual(len(config.teams), 1)
        self.assertEqual(config.teams[0].team_name, "admin-team")
        self.assertEqual(config.teams[0].access_level, "admin")
    
    def test_has_team_access(self):
        """Test team access checking."""
        config = PrivateRepositoryConfig(
            repository="buf.build/myorg/private-schemas",
            teams=[
                TeamPermission(team_name="readers", access_level="read"),
                TeamPermission(team_name="writers", access_level="write"),
                TeamPermission(team_name="admins", access_level="admin"),
            ]
        )
        
        # Test read access
        self.assertTrue(config.has_team_access("readers", "read"))
        self.assertTrue(config.has_team_access("writers", "read"))
        self.assertTrue(config.has_team_access("admins", "read"))
        
        # Test write access
        self.assertFalse(config.has_team_access("readers", "write"))
        self.assertTrue(config.has_team_access("writers", "write"))
        self.assertTrue(config.has_team_access("admins", "write"))
        
        # Test admin access
        self.assertFalse(config.has_team_access("readers", "admin"))
        self.assertFalse(config.has_team_access("writers", "admin"))
        self.assertTrue(config.has_team_access("admins", "admin"))
        
        # Test non-existent team
        self.assertFalse(config.has_team_access("nonexistent", "read"))
    
    def test_serialization(self):
        """Test configuration serialization and deserialization."""
        original_config = PrivateRepositoryConfig(
            repository="buf.build/myorg/private-schemas",
            auth_method="service_account",
            teams=[TeamPermission(team_name="team1", access_level="write")],
            service_account_file="/path/to/key.json"
        )
        
        # Convert to dict and back
        config_dict = original_config.to_dict()
        restored_config = PrivateRepositoryConfig.from_dict(config_dict)
        
        self.assertEqual(restored_config.repository, original_config.repository)
        self.assertEqual(restored_config.auth_method, original_config.auth_method)
        self.assertEqual(restored_config.service_account_file, original_config.service_account_file)
        self.assertEqual(len(restored_config.teams), 1)
        self.assertEqual(restored_config.teams[0].team_name, "team1")
        self.assertEqual(restored_config.teams[0].access_level, "write")


class TestPrivateBSRAuthenticator(unittest.TestCase):
    """Test cases for PrivateBSRAuthenticator."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir)
        self.authenticator = PrivateBSRAuthenticator(
            cache_dir=self.cache_dir,
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_configure_private_repository(self):
        """Test configuring a private repository."""
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/private-schemas",
            auth_method="service_account",
            teams=["platform-team", "backend-team"],
            service_account_file="/path/to/key.json"
        )
        
        self.assertTrue(self.authenticator.is_private_repository("buf.build/myorg/private-schemas"))
        
        config = self.authenticator.get_repository_config("buf.build/myorg/private-schemas")
        self.assertIsNotNone(config)
        self.assertEqual(config.auth_method, "service_account")
        self.assertEqual(len(config.teams), 2)
    
    def test_team_membership_management(self):
        """Test adding and removing team members."""
        # Add team members
        self.authenticator.add_team_member("alice", "platform-team")
        self.authenticator.add_team_member("bob", "platform-team")
        self.authenticator.add_team_member("alice", "backend-team")
        
        # Check memberships
        alice_teams = self.authenticator.get_user_teams("alice")
        bob_teams = self.authenticator.get_user_teams("bob")
        
        self.assertEqual(alice_teams, {"platform-team", "backend-team"})
        self.assertEqual(bob_teams, {"platform-team"})
        
        # Remove team member
        self.authenticator.remove_team_member("alice", "platform-team")
        alice_teams = self.authenticator.get_user_teams("alice")
        self.assertEqual(alice_teams, {"backend-team"})
    
    def test_repository_access_validation(self):
        """Test repository access validation."""
        # Configure private repository
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/private-schemas",
            teams=[
                TeamPermission(team_name="platform-team", access_level="read"),
                TeamPermission(team_name="admin-team", access_level="admin")
            ]
        )
        
        # Add team memberships
        self.authenticator.add_team_member("alice", "platform-team")
        self.authenticator.add_team_member("bob", "admin-team")
        
        # Test access validation
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/private-schemas", "alice", "read"
        ))
        self.assertFalse(self.authenticator.validate_repository_access(
            "buf.build/myorg/private-schemas", "alice", "write"
        ))
        
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/private-schemas", "bob", "read"
        ))
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/private-schemas", "bob", "admin"
        ))
        
        # Test non-member access
        self.assertFalse(self.authenticator.validate_repository_access(
            "buf.build/myorg/private-schemas", "charlie", "read"
        ))
        
        # Test public repository access (should always be true)
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/googleapis/googleapis", "anyone", "read"
        ))
    
    @patch.dict(os.environ, {'BUF_TOKEN': 'test-token'})
    @patch('tools.bsr_private_auth.BSRAuthenticator.authenticate')
    def test_private_repository_authentication(self, mock_authenticate):
        """Test authentication for private repositories."""
        # Mock the base authenticator
        mock_credentials = BSRCredentials(
            token="test-token",
            registry="buf.build/myorg/private-schemas"
        )
        mock_authenticate.return_value = mock_credentials
        
        # Configure private repository and team membership
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/private-schemas",
            teams=[TeamPermission(team_name="platform-team", access_level="read")]
        )
        self.authenticator.add_team_member("alice", "platform-team")
        
        # Test successful authentication
        credentials = self.authenticator.authenticate_private_repository(
            repository="buf.build/myorg/private-schemas",
            user="alice",
            required_access="read"
        )
        
        self.assertIsNotNone(credentials)
        self.assertEqual(credentials.token, "test-token")
        mock_authenticate.assert_called_once()
    
    def test_private_repository_authentication_access_denied(self):
        """Test authentication failure due to access denial."""
        # Configure private repository without giving user access
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/private-schemas",
            teams=[TeamPermission(team_name="platform-team", access_level="read")]
        )
        
        # Test access denial
        with self.assertRaises(BSRAuthenticationError):
            self.authenticator.authenticate_private_repository(
                repository="buf.build/myorg/private-schemas",
                user="charlie",  # Not a team member
                required_access="read"
            )
    
    def test_list_private_repositories(self):
        """Test listing configured private repositories."""
        # Configure multiple repositories
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/schemas1",
            teams=[TeamPermission(team_name="team1", access_level="read")]
        )
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/schemas2",
            teams=[TeamPermission(team_name="team2", access_level="write")]
        )
        
        repos = self.authenticator.list_private_repositories()
        
        self.assertEqual(len(repos), 2)
        repo_names = [repo["repository"] for repo in repos]
        self.assertIn("buf.build/myorg/schemas1", repo_names)
        self.assertIn("buf.build/myorg/schemas2", repo_names)
    
    def test_get_accessible_repositories(self):
        """Test getting repositories accessible to a user."""
        # Configure repositories
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/schemas1",
            teams=[TeamPermission(team_name="team1", access_level="read")]
        )
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/schemas2",
            teams=[TeamPermission(team_name="team2", access_level="read")]
        )
        
        # Set up user memberships
        self.authenticator.add_team_member("alice", "team1")
        self.authenticator.add_team_member("bob", "team2")
        
        # Test accessible repositories
        alice_repos = self.authenticator.get_accessible_repositories("alice")
        bob_repos = self.authenticator.get_accessible_repositories("bob")
        
        self.assertEqual(alice_repos, ["buf.build/myorg/schemas1"])
        self.assertEqual(bob_repos, ["buf.build/myorg/schemas2"])
    
    def test_remove_private_repository(self):
        """Test removing private repository configuration."""
        # Configure repository
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/private-schemas",
            teams=[TeamPermission(team_name="team1", access_level="read")]
        )
        
        self.assertTrue(self.authenticator.is_private_repository("buf.build/myorg/private-schemas"))
        
        # Remove repository
        removed = self.authenticator.remove_private_repository("buf.build/myorg/private-schemas")
        
        self.assertTrue(removed)
        self.assertFalse(self.authenticator.is_private_repository("buf.build/myorg/private-schemas"))
        
        # Try to remove non-existent repository
        removed_again = self.authenticator.remove_private_repository("buf.build/myorg/nonexistent")
        self.assertFalse(removed_again)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for private BSR authentication."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir)
        self.authenticator = PrivateBSRAuthenticator(
            cache_dir=self.cache_dir,
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_enterprise_team_workflow(self):
        """Test a complete enterprise team workflow."""
        # Configure multiple private repositories
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/platform-schemas",
            auth_method="service_account",
            teams=[
                TeamPermission(team_name="platform-team", access_level="admin"),
                TeamPermission(team_name="backend-team", access_level="read"),
                TeamPermission(team_name="frontend-team", access_level="read")
            ]
        )
        
        self.authenticator.configure_private_repository(
            repository="buf.build/myorg/internal-apis",
            auth_method="service_account",
            teams=[
                TeamPermission(team_name="backend-team", access_level="write"),
                TeamPermission(team_name="platform-team", access_level="admin")
            ]
        )
        
        # Set up team memberships
        self.authenticator.add_team_member("alice", "platform-team")
        self.authenticator.add_team_member("bob", "backend-team")
        self.authenticator.add_team_member("charlie", "frontend-team")
        
        # Test access patterns
        # Alice (platform-team) should have admin access to both
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/platform-schemas", "alice", "admin"
        ))
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/internal-apis", "alice", "admin"
        ))
        
        # Bob (backend-team) should have read access to platform, write to internal
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/platform-schemas", "bob", "read"
        ))
        self.assertFalse(self.authenticator.validate_repository_access(
            "buf.build/myorg/platform-schemas", "bob", "write"
        ))
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/internal-apis", "bob", "write"
        ))
        
        # Charlie (frontend-team) should only have read access to platform
        self.assertTrue(self.authenticator.validate_repository_access(
            "buf.build/myorg/platform-schemas", "charlie", "read"
        ))
        self.assertFalse(self.authenticator.validate_repository_access(
            "buf.build/myorg/internal-apis", "charlie", "read"
        ))
        
        # Verify accessible repositories for each user
        alice_repos = set(self.authenticator.get_accessible_repositories("alice"))
        bob_repos = set(self.authenticator.get_accessible_repositories("bob"))
        charlie_repos = set(self.authenticator.get_accessible_repositories("charlie"))
        
        expected_alice = {"buf.build/myorg/platform-schemas", "buf.build/myorg/internal-apis"}
        expected_bob = {"buf.build/myorg/platform-schemas", "buf.build/myorg/internal-apis"}
        expected_charlie = {"buf.build/myorg/platform-schemas"}
        
        self.assertEqual(alice_repos, expected_alice)
        self.assertEqual(bob_repos, expected_bob)
        self.assertEqual(charlie_repos, expected_charlie)


if __name__ == "__main__":
    unittest.main()
