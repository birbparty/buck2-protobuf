#!/usr/bin/env python3
"""
Test suite for BSR Team Management System.

This module provides comprehensive tests for team management features including
team creation, member management, repository access configuration, and
permission validation.
"""

import json
import os
import tempfile
import time
import unittest
import yaml
from pathlib import Path
from unittest.mock import Mock, patch

# Local imports
from .bsr_teams import (
    BSRTeamManager, Team, TeamMember, TeamRepository,
    TeamConfigurationError
)
from .bsr_auth import BSRAuthenticator


class TestTeamMember(unittest.TestCase):
    """Test TeamMember class functionality."""
    
    def test_create_team_member(self):
        """Test creating a team member with valid data."""
        member = TeamMember(
            username="alice",
            role="contributor",
            email="alice@example.com"
        )
        
        self.assertEqual(member.username, "alice")
        self.assertEqual(member.role, "contributor")
        self.assertEqual(member.email, "alice@example.com")
        self.assertIsNotNone(member.joined_at)
    
    def test_invalid_role(self):
        """Test that invalid roles raise ValueError."""
        with self.assertRaises(ValueError):
            TeamMember(username="bob", role="invalid_role")
    
    def test_role_permissions(self):
        """Test role-based permission checking."""
        # Test viewer permissions
        viewer = TeamMember(username="viewer", role="viewer")
        self.assertTrue(viewer._role_includes_permission("read"))
        self.assertFalse(viewer._role_includes_permission("write"))
        
        # Test contributor permissions
        contributor = TeamMember(username="contributor", role="contributor")
        self.assertTrue(contributor._role_includes_permission("read"))
        self.assertTrue(contributor._role_includes_permission("write"))
        self.assertFalse(contributor._role_includes_permission("manage"))
        
        # Test admin permissions
        admin = TeamMember(username="admin", role="admin")
        self.assertTrue(admin._role_includes_permission("read"))
        self.assertTrue(admin._role_includes_permission("write"))
        self.assertTrue(admin._role_includes_permission("manage"))
        self.assertTrue(admin._role_includes_permission("admin"))


class TestTeamRepository(unittest.TestCase):
    """Test TeamRepository class functionality."""
    
    def test_create_team_repository(self):
        """Test creating a team repository configuration."""
        repo = TeamRepository(
            repository="buf.build/myorg/schemas",
            access_level="read",
            description="Test repository"
        )
        
        self.assertEqual(repo.repository, "buf.build/myorg/schemas")
        self.assertEqual(repo.access_level, "read")
        self.assertEqual(repo.description, "Test repository")
        self.assertIsNotNone(repo.created_at)
    
    def test_invalid_access_level(self):
        """Test that invalid access levels raise ValueError."""
        with self.assertRaises(ValueError):
            TeamRepository(
                repository="buf.build/test/repo",
                access_level="invalid_access"
            )


class TestTeam(unittest.TestCase):
    """Test Team class functionality."""
    
    def setUp(self):
        """Set up test team."""
        self.team = Team(
            name="test-team",
            description="Test team for unit tests"
        )
    
    def test_create_team(self):
        """Test creating a team."""
        self.assertEqual(self.team.name, "test-team")
        self.assertEqual(self.team.description, "Test team for unit tests")
        self.assertIsNotNone(self.team.created_at)
        self.assertIsInstance(self.team.settings, dict)
    
    def test_add_member(self):
        """Test adding a member to a team."""
        member = TeamMember(username="alice", role="contributor")
        self.team.add_member(member)
        
        self.assertIn("alice", self.team.members)
        self.assertEqual(self.team.members["alice"].role, "contributor")
    
    def test_remove_member(self):
        """Test removing a member from a team."""
        member = TeamMember(username="bob", role="viewer")
        self.team.add_member(member)
        
        self.assertTrue(self.team.remove_member("bob"))
        self.assertNotIn("bob", self.team.members)
        self.assertFalse(self.team.remove_member("nonexistent"))
    
    def test_update_member_role(self):
        """Test updating a member's role."""
        member = TeamMember(username="charlie", role="viewer")
        self.team.add_member(member)
        
        self.assertTrue(self.team.update_member_role("charlie", "maintainer"))
        self.assertEqual(self.team.members["charlie"].role, "maintainer")
        self.assertFalse(self.team.update_member_role("nonexistent", "admin"))
    
    def test_add_repository(self):
        """Test adding a repository to team access."""
        repo = TeamRepository(
            repository="buf.build/test/repo",
            access_level="write"
        )
        self.team.add_repository(repo)
        
        self.assertIn("buf.build/test/repo", self.team.repositories)
        self.assertEqual(self.team.repositories["buf.build/test/repo"].access_level, "write")
    
    def test_get_effective_permissions(self):
        """Test getting effective permissions for a member."""
        # Add member and repository
        member = TeamMember(username="dev", role="contributor")
        self.team.add_member(member)
        
        repo = TeamRepository(
            repository="buf.build/test/repo",
            access_level="write"
        )
        self.team.add_repository(repo)
        
        # Test normal permissions
        permissions = self.team.get_effective_permissions("dev", "buf.build/test/repo")
        self.assertIn("read", permissions)
        self.assertIn("write", permissions)
        
        # Test with repository-specific override
        repo.team_permissions["dev"] = "admin"
        permissions = self.team.get_effective_permissions("dev", "buf.build/test/repo")
        self.assertIn("admin", permissions)
        
        # Test non-existent member
        permissions = self.team.get_effective_permissions("nonexistent", "buf.build/test/repo")
        self.assertEqual(permissions, [])


class TestBSRTeamManager(unittest.TestCase):
    """Test BSRTeamManager class functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "team-config"
        
        # Mock BSR authenticator
        self.mock_auth = Mock(spec=BSRAuthenticator)
        
        self.team_manager = BSRTeamManager(
            config_dir=self.config_dir,
            bsr_authenticator=self.mock_auth,
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_create_team(self):
        """Test creating a new team."""
        team = self.team_manager.create_team(
            name="platform-team",
            description="Platform infrastructure team"
        )
        
        self.assertEqual(team.name, "platform-team")
        self.assertIn("platform-team", self.team_manager.teams)
        
        # Test team already exists error
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.create_team(
                name="platform-team",
                description="Duplicate team"
            )
    
    def test_create_team_with_parent(self):
        """Test creating a team with a parent team."""
        # Create parent team first
        parent_team = self.team_manager.create_team(
            name="engineering",
            description="Engineering division"
        )
        
        # Create child team
        child_team = self.team_manager.create_team(
            name="backend-team",
            description="Backend development team",
            parent_team="engineering"
        )
        
        self.assertEqual(child_team.parent_team, "engineering")
        self.assertIn("backend-team", parent_team.child_teams)
        
        # Test non-existent parent error
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.create_team(
                name="orphan-team",
                description="Team with non-existent parent",
                parent_team="nonexistent-parent"
            )
    
    def test_delete_team(self):
        """Test deleting a team."""
        # Create team
        self.team_manager.create_team(
            name="temp-team",
            description="Temporary team"
        )
        
        # Delete team
        self.assertTrue(self.team_manager.delete_team("temp-team"))
        self.assertNotIn("temp-team", self.team_manager.teams)
        
        # Test deleting non-existent team
        self.assertFalse(self.team_manager.delete_team("nonexistent"))
    
    def test_delete_team_with_children(self):
        """Test deleting a team with child teams."""
        # Create parent and child teams
        self.team_manager.create_team(name="parent", description="Parent team")
        self.team_manager.create_team(
            name="child", 
            description="Child team", 
            parent_team="parent"
        )
        
        # Should fail without force
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.delete_team("parent")
        
        # Should succeed with force
        self.assertTrue(self.team_manager.delete_team("parent", force=True))
        self.assertNotIn("parent", self.team_manager.teams)
        
        # Child team should still exist but with no parent
        self.assertIsNone(self.team_manager.teams["child"].parent_team)
    
    def test_configure_team_access(self):
        """Test configuring team access to repositories."""
        # Create team
        self.team_manager.create_team(
            name="dev-team",
            description="Development team"
        )
        
        # Configure repository access
        repositories = [
            "buf.build/myorg/schemas",
            "buf.build/myorg/apis"
        ]
        self.team_manager.configure_team_access(
            team="dev-team",
            repositories=repositories,
            access_level="write"
        )
        
        team = self.team_manager.teams["dev-team"]
        self.assertEqual(len(team.repositories), 2)
        self.assertIn("buf.build/myorg/schemas", team.repositories)
        self.assertEqual(
            team.repositories["buf.build/myorg/schemas"].access_level,
            "write"
        )
        
        # Test non-existent team error
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.configure_team_access(
                team="nonexistent",
                repositories=repositories
            )
    
    def test_manage_team_members(self):
        """Test managing team members."""
        # Create team
        self.team_manager.create_team(
            name="test-team",
            description="Test team"
        )
        
        # Add members
        members = [
            {"username": "alice", "role": "maintainer", "email": "alice@example.com"},
            {"username": "bob", "role": "contributor"}
        ]
        self.team_manager.manage_team_members(
            team="test-team",
            members=members,
            action="add"
        )
        
        team = self.team_manager.teams["test-team"]
        self.assertEqual(len(team.members), 2)
        self.assertIn("alice", team.members)
        self.assertEqual(team.members["alice"].role, "maintainer")
        
        # Update member role
        self.team_manager.manage_team_members(
            team="test-team",
            members=[{"username": "bob", "role": "admin"}],
            action="update"
        )
        self.assertEqual(team.members["bob"].role, "admin")
        
        # Remove member
        self.team_manager.manage_team_members(
            team="test-team",
            members=[{"username": "alice"}],
            action="remove"
        )
        self.assertNotIn("alice", team.members)
        
        # Test non-existent team error
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.manage_team_members(
                team="nonexistent",
                members=members
            )
    
    def test_validate_team_permissions(self):
        """Test validating team permissions."""
        # Set up team with member and repository
        self.team_manager.create_team(
            name="auth-team",
            description="Authentication team"
        )
        
        self.team_manager.manage_team_members(
            team="auth-team",
            members=[{"username": "dev", "role": "contributor"}],
            action="add"
        )
        
        self.team_manager.configure_team_access(
            team="auth-team",
            repositories=["buf.build/auth/schemas"],
            access_level="write"
        )
        
        # Test team-level permissions
        self.assertTrue(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            action="read"
        ))
        
        self.assertTrue(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            action="write"
        ))
        
        self.assertFalse(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            action="admin"
        ))
        
        # Test user-specific permissions
        self.assertTrue(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            username="dev",
            action="write"
        ))
        
        self.assertFalse(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            username="dev",
            action="admin"
        ))
        
        # Test non-existent team/user/repository
        self.assertFalse(self.team_manager.validate_team_permissions(
            team="nonexistent",
            repository="buf.build/auth/schemas"
        ))
        
        self.assertFalse(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/nonexistent/repo"
        ))
        
        self.assertFalse(self.team_manager.validate_team_permissions(
            team="auth-team",
            repository="buf.build/auth/schemas",
            username="nonexistent"
        ))
    
    def test_propagate_permission_changes(self):
        """Test propagating permission changes."""
        # Set up team
        self.team_manager.create_team(
            name="ops-team",
            description="Operations team"
        )
        
        self.team_manager.manage_team_members(
            team="ops-team",
            members=[{"username": "ops-user", "role": "contributor"}],
            action="add"
        )
        
        self.team_manager.configure_team_access(
            team="ops-team",
            repositories=["buf.build/ops/configs"],
            access_level="read"
        )
        
        # Propagate changes
        changes = {
            "members": {
                "ops-user": {"role": "admin"}
            },
            "repositories": {
                "buf.build/ops/configs": {"access_level": "write"}
            }
        }
        
        result = self.team_manager.propagate_permission_changes(
            team="ops-team",
            changes=changes
        )
        
        self.assertEqual(result["team"], "ops-team")
        self.assertEqual(len(result["changes_applied"]), 2)
        self.assertEqual(len(result["errors"]), 0)
        
        # Verify changes were applied
        team = self.team_manager.teams["ops-team"]
        self.assertEqual(team.members["ops-user"].role, "admin")
        self.assertEqual(
            team.repositories["buf.build/ops/configs"].access_level,
            "write"
        )
        
        # Test non-existent team error
        with self.assertRaises(TeamConfigurationError):
            self.team_manager.propagate_permission_changes(
                team="nonexistent",
                changes=changes
            )
    
    def test_team_persistence(self):
        """Test that team configurations are saved and loaded correctly."""
        # Create team with full configuration
        self.team_manager.create_team(
            name="persistent-team",
            description="Team for persistence testing"
        )
        
        self.team_manager.manage_team_members(
            team="persistent-team",
            members=[{"username": "persistent-user", "role": "maintainer"}],
            action="add"
        )
        
        self.team_manager.configure_team_access(
            team="persistent-team",
            repositories=["buf.build/persistent/repo"],
            access_level="admin"
        )
        
        # Create new team manager instance to test loading
        new_team_manager = BSRTeamManager(
            config_dir=self.config_dir,
            bsr_authenticator=self.mock_auth
        )
        
        # Verify team was loaded correctly
        self.assertIn("persistent-team", new_team_manager.teams)
        
        team = new_team_manager.teams["persistent-team"]
        self.assertEqual(team.description, "Team for persistence testing")
        self.assertIn("persistent-user", team.members)
        self.assertEqual(team.members["persistent-user"].role, "maintainer")
        self.assertIn("buf.build/persistent/repo", team.repositories)
        self.assertEqual(
            team.repositories["buf.build/persistent/repo"].access_level,
            "admin"
        )
    
    def test_get_team_info(self):
        """Test getting comprehensive team information."""
        # Create team with members and repositories
        self.team_manager.create_team(
            name="info-team",
            description="Team for info testing"
        )
        
        self.team_manager.manage_team_members(
            team="info-team",
            members=[
                {"username": "info-user1", "role": "admin"},
                {"username": "info-user2", "role": "contributor"}
            ],
            action="add"
        )
        
        self.team_manager.configure_team_access(
            team="info-team",
            repositories=[
                "buf.build/info/repo1",
                "buf.build/info/repo2"
            ],
            access_level="write"
        )
        
        # Get team info
        team_info = self.team_manager.get_team_info("info-team")
        
        self.assertIsNotNone(team_info)
        self.assertEqual(team_info["name"], "info-team")
        self.assertEqual(team_info["member_count"], 2)
        self.assertEqual(team_info["repository_count"], 2)
        self.assertIn("info-user1", team_info["members"])
        self.assertIn("buf.build/info/repo1", team_info["repositories"])
        
        # Test non-existent team
        self.assertIsNone(self.team_manager.get_team_info("nonexistent"))
    
    def test_list_teams(self):
        """Test listing all teams."""
        # Initially no teams
        self.assertEqual(len(self.team_manager.list_teams()), 0)
        
        # Create some teams
        self.team_manager.create_team("team1", "First team")
        self.team_manager.create_team("team2", "Second team")
        
        teams = self.team_manager.list_teams()
        self.assertEqual(len(teams), 2)
        self.assertIn("team1", teams)
        self.assertIn("team2", teams)
    
    def test_get_user_teams(self):
        """Test getting teams for a specific user."""
        # Create teams and add user to some of them
        self.team_manager.create_team("team-a", "Team A")
        self.team_manager.create_team("team-b", "Team B")
        self.team_manager.create_team("team-c", "Team C")
        
        self.team_manager.manage_team_members(
            "team-a",
            [{"username": "testuser", "role": "contributor"}],
            "add"
        )
        
        self.team_manager.manage_team_members(
            "team-c",
            [{"username": "testuser", "role": "admin"}],
            "add"
        )
        
        user_teams = self.team_manager.get_user_teams("testuser")
        self.assertEqual(len(user_teams), 2)
        self.assertIn("team-a", user_teams)
        self.assertIn("team-c", user_teams)
        self.assertNotIn("team-b", user_teams)
        
        # Test non-existent user
        self.assertEqual(len(self.team_manager.get_user_teams("nonexistent")), 0)
    
    def test_get_repository_teams(self):
        """Test getting teams that have access to a repository."""
        # Create teams and configure repository access
        self.team_manager.create_team("repo-team-1", "Team 1")
        self.team_manager.create_team("repo-team-2", "Team 2")
        self.team_manager.create_team("repo-team-3", "Team 3")
        
        test_repo = "buf.build/test/shared-repo"
        
        self.team_manager.configure_team_access(
            "repo-team-1",
            [test_repo],
            "read"
        )
        
        self.team_manager.configure_team_access(
            "repo-team-3",
            [test_repo],
            "write"
        )
        
        repo_teams = self.team_manager.get_repository_teams(test_repo)
        self.assertEqual(len(repo_teams), 2)
        self.assertIn("repo-team-1", repo_teams)
        self.assertIn("repo-team-3", repo_teams)
        self.assertNotIn("repo-team-2", repo_teams)
        
        # Test non-existent repository
        self.assertEqual(
            len(self.team_manager.get_repository_teams("buf.build/nonexistent/repo")),
            0
        )


class TestIntegration(unittest.TestCase):
    """Integration tests for BSR team management."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / "integration-config"
        
        self.mock_auth = Mock(spec=BSRAuthenticator)
        self.team_manager = BSRTeamManager(
            config_dir=self.config_dir,
            bsr_authenticator=self.mock_auth
        )
    
    def tearDown(self):
        """Clean up integration test environment."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_complex_team_workflow(self):
        """Test a complex team management workflow."""
        # Create organization structure
        self.team_manager.create_team(
            "engineering",
            "Engineering division"
        )
        
        self.team_manager.create_team(
            "platform-team",
            "Platform infrastructure team",
            parent_team="engineering"
        )
        
        self.team_manager.create_team(
            "backend-team",
            "Backend development team",
            parent_team="engineering"
        )
        
        # Add team members
        platform_members = [
            {"username": "alice", "role": "admin", "email": "alice@company.com"},
            {"username": "bob", "role": "maintainer", "email": "bob@company.com"}
        ]
        
        backend_members = [
            {"username": "charlie", "role": "maintainer", "email": "charlie@company.com"},
            {"username": "diana", "role": "contributor", "email": "diana@company.com"}
        ]
        
        self.team_manager.manage_team_members("platform-team", platform_members, "add")
        self.team_manager.manage_team_members("backend-team", backend_members, "add")
        
        # Configure repository access
        platform_repos = [
            "buf.build/company/platform-schemas",
            "buf.build/company/infrastructure-types"
        ]
        
        backend_repos = [
            "buf.build/company/service-schemas",
            "buf.build/company/api-definitions"
        ]
        
        self.team_manager.configure_team_access("platform-team", platform_repos, "admin")
        self.team_manager.configure_team_access("backend-team", backend_repos, "write")
        
        # Grant backend team read access to platform schemas
        self.team_manager.configure_team_access(
            "backend-team",
            ["buf.build/company/platform-schemas"],
            "read"
        )
        
        # Validate permissions
        # Platform team admin access
        self.assertTrue(self.team_manager.validate_team_permissions(
            "platform-team",
            "buf.build/company/platform-schemas",
            "alice",
            "admin"
        ))
        
        # Backend team write access to their repos
        self.assertTrue(self.team_manager.validate_team_permissions(
            "backend-team",
            "buf.build/company/service-schemas",
            "charlie",
            "write"
        ))
        
        # Backend team read access to platform schemas
        self.assertTrue(self.team_manager.validate_team_permissions(
            "backend-team",
            "buf.build/company/platform-schemas",
            "diana",
            "read"
        ))
        
        # Backend team should not have write access to platform schemas initially
        self.assertFalse(self.team_manager.validate_team_permissions(
            "backend-team",
            "buf.build/company/platform-schemas",
            "charlie",
            "write"
        ))
        
        # Update permissions to grant write access
        changes = {
            "members": {
                "diana": {"role": "maintainer"}
            },
            "repositories": {
                "buf.build/company/platform-schemas": {"access_level": "write"}
            }
        }
        
        result = self.team_manager.propagate_permission_changes("backend-team", changes)
        self.assertEqual(len(result["changes_applied"]), 2)
        
        # Now backend team should have write access after permission changes
        self.assertTrue(self.team_manager.validate_team_permissions(
            "backend-team",
            "buf.build/company/platform-schemas",
            "charlie",
            "write"
        ))
        
        # Verify updated permissions for diana (who was promoted to maintainer)
        self.assertTrue(self.team_manager.validate_team_permissions(
            "backend-team",
            "buf.build/company/platform-schemas",
            "diana",
            "write"
        ))
        
        # Test team information
        platform_info = self.team_manager.get_team_info("platform-team")
        self.assertEqual(platform_info["parent_team"], "engineering")
        self.assertEqual(platform_info["member_count"], 2)
        self.assertEqual(platform_info["repository_count"], 2)
        
        engineering_info = self.team_manager.get_team_info("engineering")
        self.assertEqual(len(engineering_info["child_teams"]), 2)
        self.assertIn("platform-team", engineering_info["child_teams"])
        self.assertIn("backend-team", engineering_info["child_teams"])


if __name__ == "__main__":
    unittest.main()
