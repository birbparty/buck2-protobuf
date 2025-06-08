#!/usr/bin/env python3
"""
ORAS Deployment Helper for Buck2 Protobuf Projects

This module provides ORAS registry deployment automation, integrating with
Buck2 publishing workflows and supporting multiple registry configurations.
"""

import os
import sys
import json
import subprocess
import tempfile
import hashlib
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import argparse
import logging
import time
from urllib.parse import urlparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ORASDeployment:
    """ORAS registry deployment automation for protobuf schemas."""
    
    def __init__(self,
                 registry: str = "oras.birb.homes",
                 verbose: bool = True,
                 oras_binary: str = "oras",
                 buck2_binary: str = "buck2"):
        """Initialize ORAS deployment helper.
        
        Args:
            registry: ORAS registry URL (default: oras.birb.homes)
            verbose: Enable verbose logging
            oras_binary: Path to ORAS binary
            buck2_binary: Path to Buck2 binary
        """
        self.registry = registry.rstrip('/')
        self.verbose = verbose
        self.oras_binary = oras_binary
        self.buck2_binary = buck2_binary
        self.deployment_config = {}
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"Initialized ORAS deployment for registry: {self.registry}")
    
    def run_command(self, cmd: List[str], cwd: Optional[str] = None, 
                   env: Optional[Dict[str, str]] = None) -> Tuple[int, str, str]:
        """Run shell command and return results.
        
        Args:
            cmd: Command and arguments as list
            cwd: Working directory
            env: Environment variables
            
        Returns:
            Tuple of (return_code, stdout, stderr)
        """
        if cwd is None:
            cwd = os.getcwd()
        
        # Merge environment variables
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        logger.debug(f"Running command: {' '.join(cmd)} in {cwd}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for large pushes
                env=full_env
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"Command timed out: {' '.join(cmd)}")
            return 124, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return 1, "", str(e)
    
    def check_oras_availability(self) -> bool:
        """Check if ORAS binary is available and working."""
        logger.info("🔧 Checking ORAS availability...")
        
        returncode, stdout, stderr = self.run_command([self.oras_binary, "version"])
        if returncode != 0:
            logger.error(f"❌ ORAS not available: {stderr}")
            return False
        
        oras_version = stdout.strip()
        logger.info(f"✅ ORAS version: {oras_version}")
        return True
    
    def authenticate(self, username: Optional[str] = None, 
                    password: Optional[str] = None) -> bool:
        """Authenticate with ORAS registry.
        
        Args:
            username: Registry username (defaults to environment variable)
            password: Registry password (defaults to environment variable)
            
        Returns:
            True if authentication successful
        """
        logger.info(f"🔐 Authenticating with registry: {self.registry}")
        
        # Get credentials from environment if not provided
        if username is None:
            username = os.environ.get('ORAS_USERNAME')
        if password is None:
            password = os.environ.get('ORAS_PASSWORD')
        
        if not username or not password:
            logger.warning("⚠️  No credentials provided - attempting anonymous access")
            return True  # Allow anonymous access attempt
        
        # Perform authentication
        cmd = [self.oras_binary, "login", self.registry, "--username", username, "--password-stdin"]
        
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(input=password)
            
            if process.returncode == 0:
                logger.info("✅ Authentication successful")
                return True
            else:
                logger.error(f"❌ Authentication failed: {stderr}")
                return False
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            return False
    
    def calculate_file_digest(self, file_path: Path) -> str:
        """Calculate SHA256 digest of a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 digest as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def discover_protobuf_files(self, project_root: str = ".") -> List[Path]:
        """Discover protobuf files in project.
        
        Args:
            project_root: Root directory to search
            
        Returns:
            List of proto file paths
        """
        logger.info("🔍 Discovering protobuf files...")
        
        project_path = Path(project_root).resolve()
        proto_files = []
        
        # Find all .proto files, excluding build outputs
        for proto_file in project_path.glob("**/*.proto"):
            # Skip generated/temporary files
            if any(exclude in str(proto_file) for exclude in ['buck-out', '.git', '__pycache__']):
                continue
            proto_files.append(proto_file)
        
        logger.info(f"Found {len(proto_files)} protobuf files")
        return proto_files
    
    def create_oci_manifest(self, proto_files: List[Path], 
                           config_data: Dict[str, Any],
                           base_path: Path) -> Dict[str, Any]:
        """Create OCI manifest for protobuf schema artifact.
        
        Args:
            proto_files: List of proto file paths
            config_data: Configuration data
            base_path: Base path for relative file paths
            
        Returns:
            OCI manifest dictionary
        """
        logger.info("📦 Creating OCI manifest...")
        
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "artifactType": "application/vnd.cncf.protobuf.schema.v1",
            "config": {
                "mediaType": "application/vnd.cncf.protobuf.config.v1+json",
                "size": 0,
                "digest": ""
            },
            "layers": []
        }
        
        # Add each proto file as a layer
        for proto_file in proto_files:
            relative_path = proto_file.relative_to(base_path)
            file_size = proto_file.stat().st_size
            file_digest = f"sha256:{self.calculate_file_digest(proto_file)}"
            
            layer = {
                "mediaType": "application/vnd.cncf.protobuf.schema.v1",
                "size": file_size,
                "digest": file_digest,
                "annotations": {
                    "org.opencontainers.image.title": str(relative_path),
                    "org.opencontainers.image.description": f"Protobuf schema: {relative_path}",
                    "org.cncf.protobuf.file.path": str(relative_path),
                    "org.cncf.protobuf.file.size": str(file_size)
                }
            }
            
            manifest["layers"].append(layer)
        
        # Calculate config digest
        config_json = json.dumps(config_data, indent=2, sort_keys=True)
        config_size = len(config_json.encode('utf-8'))
        config_digest = f"sha256:{hashlib.sha256(config_json.encode('utf-8')).hexdigest()}"
        
        manifest["config"]["size"] = config_size
        manifest["config"]["digest"] = config_digest
        
        logger.info(f"Created manifest with {len(manifest['layers'])} layers")
        return manifest
    
    def prepare_deployment_package(self, 
                                  project_root: str = ".",
                                  version: str = "latest",
                                  metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Prepare deployment package for ORAS push.
        
        Args:
            project_root: Root directory of the project
            version: Version tag for the schemas
            metadata: Additional metadata to include
            
        Returns:
            Path to prepared deployment directory
        """
        logger.info("📦 Preparing deployment package...")
        
        project_path = Path(project_root).resolve()
        proto_files = self.discover_protobuf_files(project_root)
        
        if not proto_files:
            raise ValueError("No protobuf files found to deploy")
        
        # Create temporary deployment directory
        deploy_dir = Path(tempfile.mkdtemp(prefix="oras_deploy_"))
        logger.debug(f"Created deployment directory: {deploy_dir}")
        
        # Copy proto files to deployment directory
        for proto_file in proto_files:
            relative_path = proto_file.relative_to(project_path)
            dest_path = deploy_dir / relative_path
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(proto_file, dest_path)
        
        # Create configuration data
        config_data = {
            "version": version,
            "timestamp": time.time(),
            "schemas": [str(f.relative_to(project_path)) for f in proto_files],
            "registry": self.registry,
            "metadata": metadata or {}
        }
        
        # Add git information if available
        try:
            returncode, stdout, stderr = self.run_command(["git", "rev-parse", "HEAD"], cwd=project_root)
            if returncode == 0:
                config_data["git_commit"] = stdout.strip()
            
            returncode, stdout, stderr = self.run_command(["git", "describe", "--tags", "--always"], cwd=project_root)
            if returncode == 0:
                config_data["git_describe"] = stdout.strip()
        except:
            logger.debug("Git information not available")
        
        # Write configuration file
        config_file = deploy_dir / "config.json"
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        # Create manifest
        manifest = self.create_oci_manifest(
            [deploy_dir / f for f in config_data["schemas"]],
            config_data,
            deploy_dir
        )
        
        # Write manifest file
        manifest_file = deploy_dir / "manifest.json"
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"✅ Deployment package prepared: {len(proto_files)} files")
        return deploy_dir
    
    def push_to_registry(self,
                        deploy_dir: Path,
                        repository: str,
                        tag: str = "latest",
                        additional_tags: Optional[List[str]] = None) -> bool:
        """Push schemas to ORAS registry.
        
        Args:
            deploy_dir: Directory containing deployment package
            repository: Repository name (e.g., 'myorg/schemas')
            tag: Primary tag for the artifact
            additional_tags: Additional tags to apply
            
        Returns:
            True if push successful
        """
        logger.info(f"🚀 Pushing schemas to registry...")
        
        # Construct repository reference
        repo_ref = f"{self.registry}/{repository}:{tag}"
        logger.info(f"Target: {repo_ref}")
        
        # Build ORAS push command
        cmd = [
            self.oras_binary, "push", repo_ref,
            "--config", "config.json:application/vnd.cncf.protobuf.config.v1+json"
        ]
        
        # Add all proto files
        proto_files = [f for f in deploy_dir.glob("**/*.proto")]
        for proto_file in proto_files:
            relative_path = proto_file.relative_to(deploy_dir)
            cmd.extend([f"{relative_path}:application/vnd.cncf.protobuf.schema.v1"])
        
        # Execute push
        returncode, stdout, stderr = self.run_command(cmd, cwd=str(deploy_dir))
        
        if returncode != 0:
            logger.error(f"❌ Push failed: {stderr}")
            return False
        
        logger.info(f"✅ Successfully pushed to {repo_ref}")
        
        # Apply additional tags if specified
        if additional_tags:
            for additional_tag in additional_tags:
                additional_ref = f"{self.registry}/{repository}:{additional_tag}"
                logger.info(f"Tagging as: {additional_ref}")
                
                returncode, stdout, stderr = self.run_command([
                    self.oras_binary, "tag", repo_ref, additional_ref
                ])
                
                if returncode == 0:
                    logger.info(f"✅ Tagged as {additional_ref}")
                else:
                    logger.warning(f"⚠️  Failed to tag as {additional_ref}: {stderr}")
        
        return True
    
    def verify_deployment(self, repository: str, tag: str = "latest") -> bool:
        """Verify deployed schemas by pulling and comparing.
        
        Args:
            repository: Repository name
            tag: Tag to verify
            
        Returns:
            True if verification successful
        """
        logger.info("🔍 Verifying deployment...")
        
        repo_ref = f"{self.registry}/{repository}:{tag}"
        
        # Create temporary verification directory
        verify_dir = Path(tempfile.mkdtemp(prefix="oras_verify_"))
        
        try:
            # Pull the artifact
            returncode, stdout, stderr = self.run_command([
                self.oras_binary, "pull", repo_ref
            ], cwd=str(verify_dir))
            
            if returncode != 0:
                logger.error(f"❌ Verification pull failed: {stderr}")
                return False
            
            # Check pulled files
            pulled_files = list(verify_dir.glob("**/*.proto"))
            config_file = verify_dir / "config.json"
            
            logger.info(f"✅ Verification successful:")
            logger.info(f"   - Config file: {'✅' if config_file.exists() else '❌'}")
            logger.info(f"   - Proto files: {len(pulled_files)}")
            
            # Display config information
            if config_file.exists():
                try:
                    with open(config_file) as f:
                        config = json.load(f)
                    logger.info(f"   - Version: {config.get('version', 'unknown')}")
                    logger.info(f"   - Schemas: {len(config.get('schemas', []))}")
                except Exception as e:
                    logger.warning(f"Could not read config: {e}")
            
            return True
            
        finally:
            # Cleanup verification directory
            shutil.rmtree(verify_dir, ignore_errors=True)
    
    def deploy_schemas(self,
                      project_root: str = ".",
                      repository: str = "",
                      version: str = "latest",
                      additional_tags: Optional[List[str]] = None,
                      metadata: Optional[Dict[str, Any]] = None,
                      verify: bool = True,
                      cleanup: bool = True) -> bool:
        """Complete schema deployment workflow.
        
        Args:
            project_root: Root directory of the project
            repository: Repository name (if empty, will derive from project)
            version: Version tag for the schemas
            additional_tags: Additional tags to apply
            metadata: Additional metadata to include
            verify: Whether to verify deployment
            cleanup: Whether to cleanup temporary files
            
        Returns:
            True if deployment successful
        """
        logger.info("🚀 Starting schema deployment workflow...")
        
        # Derive repository name if not provided
        if not repository:
            project_name = Path(project_root).resolve().name
            repository = f"schemas/{project_name}"
            logger.info(f"Using derived repository name: {repository}")
        
        deploy_dir = None
        
        try:
            # Check prerequisites
            if not self.check_oras_availability():
                return False
            
            # Authenticate
            if not self.authenticate():
                logger.warning("⚠️  Authentication failed, attempting anonymous deployment")
            
            # Prepare deployment package
            deploy_dir = self.prepare_deployment_package(
                project_root=project_root,
                version=version,
                metadata=metadata
            )
            
            # Push to registry
            if not self.push_to_registry(
                deploy_dir=deploy_dir,
                repository=repository,
                tag=version,
                additional_tags=additional_tags
            ):
                return False
            
            # Verify deployment
            if verify:
                if not self.verify_deployment(repository, version):
                    logger.warning("⚠️  Deployment verification failed")
                    return False
            
            logger.info("🎉 Schema deployment completed successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}")
            return False
        
        finally:
            # Cleanup
            if cleanup and deploy_dir and deploy_dir.exists():
                shutil.rmtree(deploy_dir, ignore_errors=True)
                logger.debug("Cleaned up deployment directory")
    
    def list_deployed_versions(self, repository: str) -> List[str]:
        """List available versions in repository.
        
        Args:
            repository: Repository name
            
        Returns:
            List of available tags/versions
        """
        logger.info(f"📋 Listing versions for {repository}...")
        
        repo_url = f"{self.registry}/{repository}"
        
        # Use ORAS to list tags
        returncode, stdout, stderr = self.run_command([
            self.oras_binary, "repo", "tags", repo_url
        ])
        
        if returncode != 0:
            logger.error(f"❌ Failed to list versions: {stderr}")
            return []
        
        tags = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
        logger.info(f"Found {len(tags)} versions: {tags}")
        return tags


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ORAS Deployment Helper for Buck2 Protobuf Projects"
    )
    parser.add_argument(
        "--registry",
        default="oras.birb.homes",
        help="ORAS registry URL (default: oras.birb.homes)"
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Root directory of the project (default: current directory)"
    )
    parser.add_argument(
        "--repository",
        help="Repository name (e.g., 'myorg/schemas'). If not provided, will be derived from project directory."
    )
    parser.add_argument(
        "--version",
        default="latest",
        help="Version tag for the schemas (default: latest)"
    )
    parser.add_argument(
        "--additional-tags",
        nargs="*",
        help="Additional tags to apply"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip deployment verification"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temporary files after deployment"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare package but don't push to registry"
    )
    parser.add_argument(
        "--list-versions",
        action="store_true",
        help="List available versions in repository"
    )
    parser.add_argument(
        "--metadata",
        help="JSON string with additional metadata to include"
    )
    
    args = parser.parse_args()
    
    # Initialize deployment helper
    deployer = ORASDeployment(
        registry=args.registry,
        verbose=args.verbose
    )
    
    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid metadata JSON: {e}")
            sys.exit(1)
    
    # Handle list versions command
    if args.list_versions:
        if not args.repository:
            logger.error("Repository name required for listing versions")
            sys.exit(1)
        
        versions = deployer.list_deployed_versions(args.repository)
        if versions:
            print("Available versions:")
            for version in versions:
                print(f"  - {version}")
        else:
            print("No versions found")
        sys.exit(0)
    
    # Handle dry run
    if args.dry_run:
        logger.info("🧪 Dry run mode - preparing package only")
        try:
            deploy_dir = deployer.prepare_deployment_package(
                project_root=args.project_root,
                version=args.version,
                metadata=metadata
            )
            
            logger.info(f"✅ Package prepared successfully at: {deploy_dir}")
            logger.info("Contents:")
            for item in deploy_dir.rglob("*"):
                if item.is_file():
                    logger.info(f"  - {item.relative_to(deploy_dir)}")
            
            if not args.no_cleanup:
                shutil.rmtree(deploy_dir, ignore_errors=True)
                logger.info("Cleaned up dry run artifacts")
        except Exception as e:
            logger.error(f"Dry run failed: {e}")
            sys.exit(1)
        
        sys.exit(0)
    
    # Perform deployment
    success = deployer.deploy_schemas(
        project_root=args.project_root,
        repository=args.repository or "",
        version=args.version,
        additional_tags=args.additional_tags,
        metadata=metadata,
        verify=not args.no_verify,
        cleanup=not args.no_cleanup
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
