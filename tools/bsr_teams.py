#!/usr/bin/env python3
"""
BSR Team Management and Collaboration System.

This module provides comprehensive team management features for BSR workflows,
including team access configuration, collaborator management, and team-specific
repository organization for scalable collaboration.
"""

import argparse
import json
import os
import time
import yaml
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union, Any, Tuple
import logging

# Local imports
from .bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError
from .bsr_client import BSRClient, BSRClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TeamMember:
    """Represents a team member with roles and permissions."""
    username: str
    role: str  # viewer, contributor, maintainer, admin
    email: Optional[str] = None
    joined_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    last_active: Optional[str] = None
    permissions: Dict[str, List[str]] = field(default_factory=dict)  # repository -> [permissions]

    def __post_init__(self):
        """Validate member data."""
        valid_roles = ["viewer", "contributor", "maintainer", "admin"]
        if self.role not in valid_roles:
            raise ValueError(f"Invalid role: {self.role}. Must be one of: {valid_roles}")

    def has_permission(self, repository: str, permission: str) -> bool:
        """Check if member has specific permission for repository."""
        repo_perms = self.permissions.get(repository, [])
        return permission in repo_perms or self._role_includes_permission(permission)

    def _role_includes_permission(self, permission: str) -> bool:
        """Check if member's role includes the given permission."""
        role_permissions = {
            "viewer": ["read"],
            "contributor": ["read", "write"],
            "maintainer": ["read", "write", "manage"],
            "admin": ["read", "write", "manage", "admin"]
        }
        return permission in role_permissions.get(self.role, [])


@dataclass
class TeamRepository:
    """Represents a repository with team access configuration."""
    repository: str
    access_level: str  # read, write, admin
    team_permissions: Dict[str, str] = field(default_factory=dict)  # member -> role override
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    last_updated: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate repository data."""
        valid_access_levels = ["read", "write", "admin"]
        if self.access_level not in valid_access_levels:
            raise ValueError(f"Invalid access level: {self.access_level}. Must be one of: {valid_access_levels}")


@dataclass
class Team:
    """Represents a development team configuration."""
    name: str
    description: str
    members: Dict[str, TeamMember] = field(default_factory=dict)
    repositories: Dict[str, TeamRepository] = field(default_factory=dict)
    parent_team: Optional[str] = None
    child_teams: Set[str] = field(default_factory=set)
    created_at: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    last_updated: str = field(default_factory=lambda: time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    settings: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize team settings with defaults."""
        default_settings = {
            "auto_approve_members": False,
            "require_2fa": True,
            "default_member_role": "contributor",
            "allow_external_contributors": False,
            "notification_preferences": {
                "permission_changes": True,
                "member_additions": True,
                "repository_access": True
            }
        }
        
        for key, value in default_settings.items():
            if key not in self.settings:
                self.settings[key] = value

    def add_member(self, member: TeamMember) -> None:
        """Add a member to the team."""
        self.members[member.username] = member
        self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"Added member {member.username} to team {self.name} with role {member.role}")

    def remove_member(self, username: str) -> bool:
        """Remove a member from the team."""
        if username in self.members:
            del self.members[username]
            self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f"Removed member {username} from team {self.name}")
            return True
        return False

    def update_member_role(self, username: str, new_role: str) -> bool:
        """Update a member's role."""
        if username in self.members:
            old_role = self.members[username].role
            self.members[username].role = new_role
            self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f"Updated {username} role from {old_role} to {new_role} in team {self.name}")
            return True
        return False

    def add_repository(self, repository: TeamRepository) -> None:
        """Add a repository to team access."""
        self.repositories[repository.repository] = repository
        self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        logger.info(f"Added repository {repository.repository} to team {self.name}")

    def remove_repository(self, repository: str) -> bool:
        """Remove repository access from team."""
        if repository in self.repositories:
            del self.repositories[repository]
            self.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f"Removed repository {repository} from team {self.name}")
            return True
        return False

    def get_effective_permissions(self, username: str, repository: str) -> List[str]:
        """Get effective permissions for a member on a repository."""
        if username not in self.members:
            return []
        
        member = self.members[username]
        repo_config = self.repositories.get(repository)
        
        if not repo_config:
            return []
        
        # Check for repository-specific role override
        if username in repo_config.team_permissions:
            override_role = repo_config.team_permissions[username]
            temp_member = TeamMember(username=username, role=override_role)
            return self._get_role_permissions(temp_member.role)
        
        return self._get_role_permissions(member.role)

    def _get_role_permissions(self, role: str) -> List[str]:
        """Get permissions for a role."""
        role_permissions = {
            "viewer": ["read"],
            "contributor": ["read", "write"],
            "maintainer": ["read", "write", "manage"],
            "admin": ["read", "write", "manage", "admin"]
        }
        return role_permissions.get(role, [])


class TeamConfigurationError(Exception):
    """Team configuration operation failed."""
    pass


class BSRTeamManager:
    """
    BSR team management and collaboration system.
    
    Provides centralized management of teams, members, permissions, and
    repository access for scalable BSR collaboration workflows.
    """
    
    def __init__(self, 
                 config_dir: Union[str, Path] = None,
                 bsr_authenticator: Optional[BSRAuthenticator] = None,
                 verbose: bool = False):
        """
        Initialize BSR Team Manager.
        
        Args:
            config_dir: Directory for team configuration storage
            bsr_authenticator: BSR authentication instance
            verbose: Enable verbose logging
        """
        if config_dir is None:
            config_dir = Path.home() / '.cache' / 'buck2-protobuf' / 'team-config'
        
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.verbose = verbose
        self.teams: Dict[str, Team] = {}
        
        # Team configuration file
        self.teams_config_file = self.config_dir / "teams.yaml"
        
        # BSR authentication
        self.bsr_authenticator = bsr_authenticator or BSRAuthenticator(verbose=verbose)
        
        # Load existing team configurations
        self._load_teams_config()
        
        logger.info(f"BSR Team Manager initialized with {len(self.teams)} teams")

    def _load_teams_config(self) -> None:
        """Load team configurations from storage."""
        if not self.teams_config_file.exists():
            return
        
        try:
            with open(self.teams_config_file, 'r') as f:
                teams_data = yaml.safe_load(f) or {}
            
            for team_name, team_data in teams_data.items():
                # Convert member data to TeamMember objects
                members = {}
                for username, member_data in team_data.get('members', {}).items():
                    members[username] = TeamMember(**member_data)
                
                # Convert repository data to TeamRepository objects
                repositories = {}
                for repo_name, repo_data in team_data.get('repositories', {}).items():
                    repositories[repo_name] = TeamRepository(**repo_data)
                
                # Create team object
                team_data['members'] = members
                team_data['repositories'] = repositories
                team_data['child_teams'] = set(team_data.get('child_teams', []))
                
                self.teams[team_name] = Team(**team_data)
                
            logger.info(f"Loaded {len(self.teams)} team configurations")
            
        except Exception as e:
            logger.error(f"Failed to load team configurations: {e}")

    def _save_teams_config(self) -> None:
        """Save team configurations to storage."""
        try:
            teams_data = {}
            
            for team_name, team in self.teams.items():
                # Convert TeamMember objects to dicts
                members_data = {}
                for username, member in team.members.items():
                    members_data[username] = asdict(member)
                
                # Convert TeamRepository objects to dicts
                repositories_data = {}
                for repo_name, repo in team.repositories.items():
                    repositories_data[repo_name] = asdict(repo)
                
                # Convert team to dict
                team_data = asdict(team)
                team_data['members'] = members_data
                team_data['repositories'] = repositories_data
                team_data['child_teams'] = list(team.child_teams)
                
                teams_data[team_name] = team_data
            
            with open(self.teams_config_file, 'w') as f:
                yaml.dump(teams_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"Saved {len(self.teams)} team configurations")
            
        except Exception as e:
            logger.error(f"Failed to save team configurations: {e}")
            raise TeamConfigurationError(f"Failed to save team configurations: {e}")

    def create_team(self, 
                   name: str, 
                   description: str,
                   parent_team: Optional[str] = None,
                   settings: Optional[Dict[str, Any]] = None) -> Team:
        """
        Create a new team.
        
        Args:
            name: Team name
            description: Team description
            parent_team: Parent team name for hierarchical teams
            settings: Team-specific settings
            
        Returns:
            Created team object
            
        Raises:
            TeamConfigurationError: If team creation fails
        """
        if name in self.teams:
            raise TeamConfigurationError(f"Team '{name}' already exists")
        
        if parent_team and parent_team not in self.teams:
            raise TeamConfigurationError(f"Parent team '{parent_team}' does not exist")
        
        team = Team(
            name=name,
            description=description,
            parent_team=parent_team,
            settings=settings or {}
        )
        
        self.teams[name] = team
        
        # Update parent team if specified
        if parent_team:
            self.teams[parent_team].child_teams.add(name)
        
        self._save_teams_config()
        logger.info(f"Created team '{name}' with parent '{parent_team}'")
        
        return team

    def delete_team(self, name: str, force: bool = False) -> bool:
        """
        Delete a team.
        
        Args:
            name: Team name to delete
            force: Force deletion even if team has child teams
            
        Returns:
            True if team was deleted
            
        Raises:
            TeamConfigurationError: If deletion fails
        """
        if name not in self.teams:
            return False
        
        team = self.teams[name]
        
        # Check for child teams
        if team.child_teams and not force:
            raise TeamConfigurationError(
                f"Team '{name}' has child teams: {list(team.child_teams)}. "
                "Use force=True to delete anyway."
            )
        
        # Remove from parent team
        if team.parent_team and team.parent_team in self.teams:
            self.teams[team.parent_team].child_teams.discard(name)
        
        # Update child teams
        for child_team_name in team.child_teams:
            if child_team_name in self.teams:
                self.teams[child_team_name].parent_team = team.parent_team
                if team.parent_team:
                    self.teams[team.parent_team].child_teams.add(child_team_name)
        
        del self.teams[name]
        self._save_teams_config()
        logger.info(f"Deleted team '{name}'")
        
        return True

    def configure_team_access(self, 
                            team: str, 
                            repositories: List[str],
                            access_level: str = "read") -> None:
        """
        Configure team access to BSR repositories.
        
        Args:
            team: Team name
            repositories: List of repository references
            access_level: Default access level for repositories
            
        Raises:
            TeamConfigurationError: If configuration fails
        """
        if team not in self.teams:
            raise TeamConfigurationError(f"Team '{team}' does not exist")
        
        team_obj = self.teams[team]
        
        for repository in repositories:
            repo_config = TeamRepository(
                repository=repository,
                access_level=access_level,
                description=f"Repository access for team {team}"
            )
            team_obj.add_repository(repo_config)
        
        self._save_teams_config()
        logger.info(f"Configured access to {len(repositories)} repositories for team '{team}'")

    def manage_team_members(self, 
                          team: str, 
                          members: List[Dict[str, str]],
                          action: str = "add") -> None:
        """
        Manage team membership and permissions.
        
        Args:
            team: Team name
            members: List of member configurations [{"username": "user", "role": "contributor"}]
            action: Action to perform ("add", "remove", "update")
            
        Raises:
            TeamConfigurationError: If operation fails
        """
        if team not in self.teams:
            raise TeamConfigurationError(f"Team '{team}' does not exist")
        
        team_obj = self.teams[team]
        
        for member_config in members:
            username = member_config.get('username')
            role = member_config.get('role', 'contributor')
            
            if not username:
                continue
            
            if action == "add":
                member = TeamMember(
                    username=username,
                    role=role,
                    email=member_config.get('email')
                )
                team_obj.add_member(member)
                
            elif action == "remove":
                team_obj.remove_member(username)
                
            elif action == "update":
                team_obj.update_member_role(username, role)
        
        self._save_teams_config()
        logger.info(f"Managed {len(members)} members for team '{team}' (action: {action})")

    def organize_team_repositories(self, 
                                 team: str, 
                                 organization: Dict[str, Any]) -> None:
        """
        Organize repositories for team workflows.
        
        Args:
            team: Team name
            organization: Repository organization configuration
            
        Raises:
            TeamConfigurationError: If organization fails
        """
        if team not in self.teams:
            raise TeamConfigurationError(f"Team '{team}' does not exist")
        
        team_obj = self.teams[team]
        
        # Update repository configurations based on organization
        for repo_name, config in organization.items():
            if repo_name in team_obj.repositories:
                repo = team_obj.repositories[repo_name]
                
                # Update description
                if 'description' in config:
                    repo.description = config['description']
                
                # Update tags
                if 'tags' in config:
                    repo.tags = config['tags']
                
                # Update team-specific permissions
                if 'team_permissions' in config:
                    repo.team_permissions.update(config['team_permissions'])
                
                repo.last_updated = time.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        self._save_teams_config()
        logger.info(f"Organized {len(organization)} repositories for team '{team}'")

    def validate_team_permissions(self, 
                                team: str, 
                                repository: str,
                                username: str = None,
                                action: str = "read") -> bool:
        """
        Validate team permissions for repository access.
        
        Args:
            team: Team name
            repository: Repository reference
            username: Specific username to check (optional)
            action: Action to validate ("read", "write", "manage", "admin")
            
        Returns:
            True if permission is valid
        """
        if team not in self.teams:
            return False
        
        team_obj = self.teams[team]
        
        # Check if repository is accessible to team
        if repository not in team_obj.repositories:
            return False
        
        # If username specified, check specific member permissions
        if username:
            if username not in team_obj.members:
                return False
            
            # Check both team access level and user permissions
            repo_config = team_obj.repositories[repository]
            team_access_permissions = {
                "read": ["read"],
                "write": ["read", "write"],
                "admin": ["read", "write", "manage", "admin"]
            }
            
            # Team must have sufficient access level for the action
            team_allowed_actions = team_access_permissions.get(repo_config.access_level, [])
            if action not in team_allowed_actions:
                return False
            
            # User must also have sufficient role permissions
            permissions = team_obj.get_effective_permissions(username, repository)
            return action in permissions
        
        # Check team-level access
        repo_config = team_obj.repositories[repository]
        access_level_permissions = {
            "read": ["read"],
            "write": ["read", "write"],
            "admin": ["read", "write", "manage", "admin"]
        }
        
        allowed_actions = access_level_permissions.get(repo_config.access_level, [])
        return action in allowed_actions

    def propagate_permission_changes(self, 
                                   team: str, 
                                   changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Propagate permission changes across team and repositories.
        
        Args:
            team: Team name
            changes: Permission change configuration
            
        Returns:
            Result of propagation operation
        """
        if team not in self.teams:
            raise TeamConfigurationError(f"Team '{team}' does not exist")
        
        team_obj = self.teams[team]
        propagation_result = {
            "team": team,
            "changes_applied": [],
            "errors": [],
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
        
        try:
            # Apply member changes
            if 'members' in changes:
                for username, member_changes in changes['members'].items():
                    if username in team_obj.members:
                        member = team_obj.members[username]
                        
                        if 'role' in member_changes:
                            old_role = member.role
                            member.role = member_changes['role']
                            propagation_result["changes_applied"].append({
                                "type": "member_role_change",
                                "username": username,
                                "old_role": old_role,
                                "new_role": member.role
                            })
                        
                        if 'permissions' in member_changes:
                            member.permissions.update(member_changes['permissions'])
                            propagation_result["changes_applied"].append({
                                "type": "member_permissions_update",
                                "username": username,
                                "permissions": member_changes['permissions']
                            })
            
            # Apply repository changes
            if 'repositories' in changes:
                for repo_name, repo_changes in changes['repositories'].items():
                    if repo_name in team_obj.repositories:
                        repo = team_obj.repositories[repo_name]
                        
                        if 'access_level' in repo_changes:
                            old_access = repo.access_level
                            repo.access_level = repo_changes['access_level']
                            propagation_result["changes_applied"].append({
                                "type": "repository_access_change",
                                "repository": repo_name,
                                "old_access": old_access,
                                "new_access": repo.access_level
                            })
                        
                        if 'team_permissions' in repo_changes:
                            repo.team_permissions.update(repo_changes['team_permissions'])
                            propagation_result["changes_applied"].append({
                                "type": "repository_permissions_update",
                                "repository": repo_name,
                                "permissions": repo_changes['team_permissions']
                            })
            
            # Update team timestamp
            team_obj.last_updated = propagation_result["timestamp"]
            
            # Save changes
            self._save_teams_config()
            
            logger.info(f"Propagated {len(propagation_result['changes_applied'])} changes for team '{team}'")
            
        except Exception as e:
            error_msg = f"Failed to propagate changes: {e}"
            propagation_result["errors"].append(error_msg)
            logger.error(error_msg)
        
        return propagation_result

    def get_team_info(self, team: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive team information."""
        if team not in self.teams:
            return None
        
        team_obj = self.teams[team]
        
        return {
            "name": team_obj.name,
            "description": team_obj.description,
            "member_count": len(team_obj.members),
            "repository_count": len(team_obj.repositories),
            "parent_team": team_obj.parent_team,
            "child_teams": list(team_obj.child_teams),
            "created_at": team_obj.created_at,
            "last_updated": team_obj.last_updated,
            "settings": team_obj.settings,
            "members": {
                username: {
                    "role": member.role,
                    "email": member.email,
                    "joined_at": member.joined_at,
                    "last_active": member.last_active
                }
                for username, member in team_obj.members.items()
            },
            "repositories": {
                repo_name: {
                    "access_level": repo.access_level,
                    "description": repo.description,
                    "tags": repo.tags,
                    "created_at": repo.created_at,
                    "last_updated": repo.last_updated
                }
                for repo_name, repo in team_obj.repositories.items()
            }
        }

    def list_teams(self) -> List[str]:
        """List all configured teams."""
        return list(self.teams.keys())

    def get_user_teams(self, username: str) -> List[str]:
        """Get teams that a user belongs to."""
        user_teams = []
        
        for team_name, team in self.teams.items():
            if username in team.members:
                user_teams.append(team_name)
        
        return user_teams

    def get_repository_teams(self, repository: str) -> List[str]:
        """Get teams that have access to a repository."""
        repo_teams = []
        
        for team_name, team in self.teams.items():
            if repository in team.repositories:
                repo_teams.append(team_name)
        
        return repo_teams


def main():
    """Main entry point for BSR team management testing."""
    parser = argparse.ArgumentParser(description="BSR Team Management System")
    parser.add_argument("--config-dir", help="Configuration directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Create team
    create_parser = subparsers.add_parser("create", help="Create a new team")
    create_parser.add_argument("--name", required=True, help="Team name")
    create_parser.add_argument("--description", required=True, help="Team description")
    create_parser.add_argument("--parent", help="Parent team name")
    
    # Add member
    member_parser = subparsers.add_parser("add-member", help="Add member to team")
    member_parser.add_argument("--team", required=True, help="Team name")
    member_parser.add_argument("--username", required=True, help="Username")
    member_parser.add_argument("--role", default="contributor", help="Member role")
    member_parser.add_argument("--email", help="Member email")
    
    # Configure repository access
    repo_parser = subparsers.add_parser("add-repo", help="Add repository access")
    repo_parser.add_argument("--team", required=True, help="Team name")
    repo_parser.add_argument("--repository", required=True, help="Repository reference")
    repo_parser.add_argument("--access", default="read", help="Access level")
    
    # List teams
    list_parser = subparsers.add_parser("list", help="List teams")
    
    # Team info
    info_parser = subparsers.add_parser("info", help="Show team information")
    info_parser.add_argument("--team", required=True, help="Team name")
    
    # Validate permissions
    validate_parser = subparsers.add_parser("validate", help="Validate permissions")
    validate_parser.add_argument("--team", required=True, help="Team name")
    validate_parser.add_argument("--repository", required=True, help="Repository")
    validate_parser.add_argument("--username", help="Username to check")
    validate_parser.add_argument("--action", default="read", help="Action to validate")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        team_manager = BSRTeamManager(
            config_dir=args.config_dir,
            verbose=args.verbose
        )
        
        if args.command == "create":
            team = team_manager.create_team(
                name=args.name,
                description=args.description,
                parent_team=args.parent
            )
            print(f"✅ Created team '{team.name}'")
        
        elif args.command == "add-member":
            members = [{
                "username": args.username,
                "role": args.role,
                "email": args.email
            }]
            team_manager.manage_team_members(args.team, members, action="add")
            print(f"✅ Added {args.username} to team '{args.team}' as {args.role}")
        
        elif args.command == "add-repo":
            team_manager.configure_team_access(
                team=args.team,
                repositories=[args.repository],
                access_level=args.access
            )
            print(f"✅ Added repository '{args.repository}' to team '{args.team}' with {args.access} access")
        
        elif args.command == "list":
            teams = team_manager.list_teams()
            if teams:
                print(f"Configured teams ({len(teams)}):")
                for team_name in teams:
                    team_info = team_manager.get_team_info(team_name)
                    print(f"  {team_name}: {team_info['member_count']} members, {team_info['repository_count']} repositories")
            else:
                print("No teams configured")
        
        elif args.command == "info":
            team_info = team_manager.get_team_info(args.team)
            if team_info:
                print(f"Team: {team_info['name']}")
                print(f"Description: {team_info['description']}")
                print(f"Members: {team_info['member_count']}")
                print(f"Repositories: {team_info['repository_count']}")
                print(f"Created: {team_info['created_at']}")
                print(f"Last Updated: {team_info['last_updated']}")
                
                if team_info['members']:
                    print("\nMembers:")
                    for username, member in team_info['members'].items():
                        print(f"  {username} ({member['role']})")
                
                if team_info['repositories']:
                    print("\nRepositories:")
                    for repo, config in team_info['repositories'].items():
                        print(f"  {repo} ({config['access_level']})")
            else:
                print(f"Team '{args.team}' not found")
        
        elif args.command == "validate":
            is_valid = team_manager.validate_team_permissions(
                team=args.team,
                repository=args.repository,
                username=args.username,
                action=args.action
            )
            
            if is_valid:
                user_part = f" for user {args.username}" if args.username else ""
                print(f"✅ Permission '{args.action}' valid for team '{args.team}' on repository '{args.repository}'{user_part}")
            else:
                user_part = f" for user {args.username}" if args.username else ""
                print(f"❌ Permission '{args.action}' denied for team '{args.team}' on repository '{args.repository}'{user_part}")
                return 1
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
