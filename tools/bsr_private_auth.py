#!/usr/bin/env python3
"""
Private BSR Repository Authentication with Team-Based Access Control.

This module extends the BSR authentication system to support private repositories
with team-based permissions, repository-specific credentials, and enhanced
access control validation.
"""

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Union

try:
    from .bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError
    from .bsr_client import BSRClient
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(str(Path(__file__).parent))
    from bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError
    from bsr_client import BSRClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TeamPermission:
    """Team permission configuration for BSR repositories."""
    team_name: str
    access_level: str  # "read", "write", "admin"
    granted_at: Optional[float] = None
    granted_by: Optional[str] = None
    
    def __post_init__(self):
        """Initialize permission metadata."""
        if self.granted_at is None:
            self.granted_at = time.time()
        
        if self.access_level not in ["read", "write", "admin"]:
            raise ValueError(f"Invalid access level: {self.access_level}")


@dataclass
class PrivateRepositoryConfig:
    """Configuration for a private BSR repository."""
    repository: str
    auth_method: str = "auto"
    teams: List[TeamPermission] = None
    service_account_file: Optional[str] = None
    cache_ttl: int = 3600
    created_at: Optional[float] = None
    
    def __post_init__(self):
        """Initialize repository configuration."""
        if self.teams is None:
            self.teams = []
        
        if self.created_at is None:
            self.created_at = time.time()
        
        # Convert team strings to TeamPermission objects if needed
        processed_teams = []
        for team in self.teams:
            if isinstance(team, str):
                # Default to read access for string team names
                processed_teams.append(TeamPermission(team_name=team, access_level="read"))
            elif isinstance(team, dict):
                processed_teams.append(TeamPermission(**team))
            elif isinstance(team, TeamPermission):
                processed_teams.append(team)
            else:
                raise ValueError(f"Invalid team specification: {team}")
        
        self.teams = processed_teams

    def has_team_access(self, team_name: str, required_access: str = "read") -> bool:
        """Check if a team has the required access level."""
        access_levels = {"read": 1, "write": 2, "admin": 3}
        required_level = access_levels.get(required_access, 1)
        
        for team in self.teams:
            if team.team_name == team_name:
                team_level = access_levels.get(team.access_level, 0)
                return team_level >= required_level
        
        return False

    def get_team_access_level(self, team_name: str) -> Optional[str]:
        """Get the access level for a specific team."""
        for team in self.teams:
            if team.team_name == team_name:
                return team.access_level
        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert TeamPermission objects to dicts
        data["teams"] = [asdict(team) for team in self.teams]
        return data

    @classmethod
    def from_dict(cls, data: Dict) -> 'PrivateRepositoryConfig':
        """Create from dictionary."""
        teams_data = data.get("teams", [])
        teams = [TeamPermission(**team) if isinstance(team, dict) else team for team in teams_data]
        data["teams"] = teams
        return cls(**data)


class PrivateBSRAuthenticator(BSRAuthenticator):
    """
    Enhanced BSR authenticator with private repository and team support.
    
    Extends the base BSR authenticator to handle private repositories with
    team-based access control, repository-specific authentication, and
    enhanced permission validation.
    """
    
    def __init__(self, 
                 cache_dir: Union[str, Path] = None,
                 registry: str = "buf.build",
                 verbose: bool = False):
        """
        Initialize private BSR authenticator.
        
        Args:
            cache_dir: Directory for credential and configuration caching
            registry: Default BSR registry
            verbose: Enable verbose logging
        """
        super().__init__(cache_dir, registry, verbose)
        
        # Private repository configurations
        self.private_repo_configs: Dict[str, PrivateRepositoryConfig] = {}
        self.repo_configs_cache = self.cache_dir / 'private_repo_configs.json'
        
        # Team membership cache
        self.team_cache = self.cache_dir / 'team_memberships.json'
        self.team_memberships: Dict[str, Set[str]] = {}
        
        # Load existing configurations
        self._load_private_repo_configs()
        self._load_team_memberships()
        
        if self.verbose:
            logger.info("PrivateBSRAuthenticator initialized with private repository support")

    def _load_private_repo_configs(self) -> None:
        """Load private repository configurations from cache."""
        if self.repo_configs_cache.exists():
            try:
                with open(self.repo_configs_cache) as f:
                    configs_data = json.load(f)
                
                for repo, config_data in configs_data.items():
                    self.private_repo_configs[repo] = PrivateRepositoryConfig.from_dict(config_data)
                
                self.log(f"Loaded {len(self.private_repo_configs)} private repository configurations")
            except Exception as e:
                self.log(f"Failed to load private repo configs: {e}")

    def _save_private_repo_configs(self) -> None:
        """Save private repository configurations to cache."""
        try:
            configs_data = {}
            for repo, config in self.private_repo_configs.items():
                configs_data[repo] = config.to_dict()
            
            with open(self.repo_configs_cache, 'w') as f:
                json.dump(configs_data, f, indent=2)
            
            self.log("Saved private repository configurations")
        except Exception as e:
            self.log(f"Failed to save private repo configs: {e}")

    def _load_team_memberships(self) -> None:
        """Load team membership information from cache."""
        if self.team_cache.exists():
            try:
                with open(self.team_cache) as f:
                    memberships_data = json.load(f)
                
                for user, teams in memberships_data.items():
                    self.team_memberships[user] = set(teams)
                
                self.log(f"Loaded team memberships for {len(self.team_memberships)} users")
            except Exception as e:
                self.log(f"Failed to load team memberships: {e}")

    def _save_team_memberships(self) -> None:
        """Save team membership information to cache."""
        try:
            memberships_data = {}
            for user, teams in self.team_memberships.items():
                memberships_data[user] = list(teams)
            
            with open(self.team_cache, 'w') as f:
                json.dump(memberships_data, f, indent=2)
            
            self.log("Saved team memberships")
        except Exception as e:
            self.log(f"Failed to save team memberships: {e}")

    def configure_private_repository(self, 
                                   repository: str,
                                   auth_method: str = "auto",
                                   teams: List[Union[str, Dict, TeamPermission]] = None,
                                   service_account_file: Optional[str] = None,
                                   cache_ttl: int = 3600) -> None:
        """
        Configure a private BSR repository with team-based access control.
        
        Args:
            repository: BSR repository reference
            auth_method: Authentication method to use
            teams: List of teams with access (strings, dicts, or TeamPermission objects)
            service_account_file: Path to service account key file
            cache_ttl: Cache time-to-live in seconds
        """
        config = PrivateRepositoryConfig(
            repository=repository,
            auth_method=auth_method,
            teams=teams or [],
            service_account_file=service_account_file,
            cache_ttl=cache_ttl
        )
        
        self.private_repo_configs[repository] = config
        self._save_private_repo_configs()
        
        self.log(f"Configured private repository: {repository} with {len(config.teams)} teams")

    def add_team_member(self, user: str, team: str) -> None:
        """Add a user to a team."""
        if user not in self.team_memberships:
            self.team_memberships[user] = set()
        
        self.team_memberships[user].add(team)
        self._save_team_memberships()
        
        self.log(f"Added user {user} to team {team}")

    def remove_team_member(self, user: str, team: str) -> None:
        """Remove a user from a team."""
        if user in self.team_memberships:
            self.team_memberships[user].discard(team)
            if not self.team_memberships[user]:
                del self.team_memberships[user]
            
            self._save_team_memberships()
            self.log(f"Removed user {user} from team {team}")

    def get_user_teams(self, user: str) -> Set[str]:
        """Get teams that a user belongs to."""
        return self.team_memberships.get(user, set())

    def is_private_repository(self, repository: str) -> bool:
        """Check if a repository is configured as private."""
        return repository in self.private_repo_configs

    def validate_repository_access(self, 
                                 repository: str, 
                                 user: str = None,
                                 required_access: str = "read") -> bool:
        """
        Validate that a user has access to a private repository.
        
        Args:
            repository: BSR repository reference
            user: Username (if None, uses current user from environment)
            required_access: Required access level ("read", "write", "admin")
            
        Returns:
            True if access is granted, False otherwise
        """
        if not self.is_private_repository(repository):
            # Public repository - always accessible
            return True
        
        config = self.private_repo_configs[repository]
        
        # If no teams configured, deny access (private but misconfigured)
        if not config.teams:
            self.log(f"No teams configured for private repository: {repository}")
            return False
        
        # Determine user (from parameter, environment, or credentials)
        if not user:
            user = os.getenv('USER') or os.getenv('USERNAME') or 'unknown'
        
        # Get user's teams
        user_teams = self.get_user_teams(user)
        
        # Check if user has required access through any team
        for team_perm in config.teams:
            if team_perm.team_name in user_teams:
                if self._has_sufficient_access(team_perm.access_level, required_access):
                    self.log(f"Access granted to {repository} for user {user} via team {team_perm.team_name}")
                    return True
        
        self.log(f"Access denied to {repository} for user {user} (teams: {user_teams})")
        return False

    def _has_sufficient_access(self, user_access: str, required_access: str) -> bool:
        """Check if user access level meets requirement."""
        access_levels = {"read": 1, "write": 2, "admin": 3}
        user_level = access_levels.get(user_access, 0)
        required_level = access_levels.get(required_access, 1)
        return user_level >= required_level

    def authenticate_private_repository(self, 
                                      repository: str,
                                      user: str = None,
                                      required_access: str = "read",
                                      **kwargs) -> BSRCredentials:
        """
        Authenticate access to a private BSR repository.
        
        Args:
            repository: BSR repository reference
            user: Username for access validation
            required_access: Required access level
            **kwargs: Additional authentication parameters
            
        Returns:
            BSR credentials for the repository
            
        Raises:
            BSRAuthenticationError: If authentication or access validation fails
        """
        # Validate repository access first
        if not self.validate_repository_access(repository, user, required_access):
            raise BSRAuthenticationError(f"Access denied to private repository: {repository}")
        
        # Get repository configuration
        if self.is_private_repository(repository):
            config = self.private_repo_configs[repository]
            auth_method = config.auth_method
            service_account_file = config.service_account_file
            
            # Use repository-specific authentication settings
            if service_account_file and auth_method == "service_account":
                kwargs["service_account_file"] = service_account_file
        else:
            auth_method = kwargs.get("method", "auto")
        
        # Authenticate using the base authenticator
        credentials = self.authenticate(
            repository=repository,
            method=auth_method,
            **kwargs
        )
        
        # Add repository access information to credentials
        if hasattr(credentials, 'repository_access'):
            if not credentials.repository_access:
                credentials.repository_access = []
            credentials.repository_access.append(repository)
        
        return credentials

    def list_private_repositories(self) -> List[Dict]:
        """List all configured private repositories."""
        repositories = []
        
        for repo, config in self.private_repo_configs.items():
            repo_info = {
                "repository": repo,
                "auth_method": config.auth_method,
                "teams": [{"team": team.team_name, "access": team.access_level} for team in config.teams],
                "created_at": config.created_at,
                "cache_ttl": config.cache_ttl
            }
            repositories.append(repo_info)
        
        return repositories

    def get_repository_config(self, repository: str) -> Optional[PrivateRepositoryConfig]:
        """Get configuration for a private repository."""
        return self.private_repo_configs.get(repository)

    def remove_private_repository(self, repository: str) -> bool:
        """Remove private repository configuration."""
        if repository in self.private_repo_configs:
            del self.private_repo_configs[repository]
            self._save_private_repo_configs()
            
            # Also clear any cached credentials for this repository
            self.logout(repository)
            
            self.log(f"Removed private repository configuration: {repository}")
            return True
        
        return False

    def get_accessible_repositories(self, user: str = None) -> List[str]:
        """Get list of repositories accessible to a user."""
        if not user:
            user = os.getenv('USER') or os.getenv('USERNAME') or 'unknown'
        
        accessible = []
        
        for repo, config in self.private_repo_configs.items():
            if self.validate_repository_access(repo, user, "read"):
                accessible.append(repo)
        
        return accessible


def main():
    """Main entry point for private BSR authentication testing."""
    parser = argparse.ArgumentParser(description="Private BSR Authentication with Team Access Control")
    parser.add_argument("--registry", default="buf.build", help="BSR registry URL")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Configure repository command
    config_parser = subparsers.add_parser("configure", help="Configure private repository")
    config_parser.add_argument("repository", help="Repository reference")
    config_parser.add_argument("--auth-method", default="auto", help="Authentication method")
    config_parser.add_argument("--teams", nargs="+", help="Teams with access")
    config_parser.add_argument("--service-account-file", help="Service account key file")
    
    # Add team member command
    team_add_parser = subparsers.add_parser("add-team-member", help="Add user to team")
    team_add_parser.add_argument("user", help="Username")
    team_add_parser.add_argument("team", help="Team name")
    
    # Remove team member command
    team_remove_parser = subparsers.add_parser("remove-team-member", help="Remove user from team")
    team_remove_parser.add_argument("user", help="Username")
    team_remove_parser.add_argument("team", help="Team name")
    
    # Validate access command
    validate_parser = subparsers.add_parser("validate-access", help="Validate repository access")
    validate_parser.add_argument("repository", help="Repository reference")
    validate_parser.add_argument("--user", help="Username to check")
    validate_parser.add_argument("--access-level", default="read", help="Required access level")
    
    # List repositories command
    list_parser = subparsers.add_parser("list-repos", help="List private repositories")
    
    # List accessible repositories command
    accessible_parser = subparsers.add_parser("list-accessible", help="List accessible repositories")
    accessible_parser.add_argument("--user", help="Username to check")
    
    # Authenticate command
    auth_parser = subparsers.add_parser("auth", help="Authenticate to private repository")
    auth_parser.add_argument("repository", help="Repository reference")
    auth_parser.add_argument("--user", help="Username")
    auth_parser.add_argument("--access-level", default="read", help="Required access level")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        authenticator = PrivateBSRAuthenticator(
            cache_dir=args.cache_dir,
            registry=args.registry,
            verbose=args.verbose
        )
        
        if args.command == "configure":
            teams = []
            if args.teams:
                for team in args.teams:
                    # Support team:access format
                    if ":" in team:
                        team_name, access_level = team.split(":", 1)
                        teams.append(TeamPermission(team_name=team_name, access_level=access_level))
                    else:
                        teams.append(TeamPermission(team_name=team, access_level="read"))
            
            authenticator.configure_private_repository(
                repository=args.repository,
                auth_method=args.auth_method,
                teams=teams,
                service_account_file=args.service_account_file
            )
            print(f"✅ Configured private repository: {args.repository}")
        
        elif args.command == "add-team-member":
            authenticator.add_team_member(args.user, args.team)
            print(f"✅ Added {args.user} to team {args.team}")
        
        elif args.command == "remove-team-member":
            authenticator.remove_team_member(args.user, args.team)
            print(f"✅ Removed {args.user} from team {args.team}")
        
        elif args.command == "validate-access":
            if authenticator.validate_repository_access(args.repository, args.user, args.access_level):
                print(f"✅ Access granted to {args.repository}")
            else:
                print(f"❌ Access denied to {args.repository}")
                return 1
        
        elif args.command == "list-repos":
            repos = authenticator.list_private_repositories()
            if repos:
                print(f"Private repositories ({len(repos)}):")
                for repo in repos:
                    teams_info = ", ".join([f"{t['team']}:{t['access']}" for t in repo['teams']])
                    print(f"  {repo['repository']} (teams: {teams_info})")
            else:
                print("No private repositories configured")
        
        elif args.command == "list-accessible":
            accessible = authenticator.get_accessible_repositories(args.user)
            user_name = args.user or "current user"
            if accessible:
                print(f"Repositories accessible to {user_name} ({len(accessible)}):")
                for repo in accessible:
                    print(f"  {repo}")
            else:
                print(f"No repositories accessible to {user_name}")
        
        elif args.command == "auth":
            credentials = authenticator.authenticate_private_repository(
                repository=args.repository,
                user=args.user,
                required_access=args.access_level
            )
            print(f"✅ Successfully authenticated to {args.repository}")
            print(f"   Method: {credentials.auth_method}")
            print(f"   Token: {credentials.mask_token()}")
    
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
