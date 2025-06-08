#!/usr/bin/env python3
"""
Cargo (Rust) plugin installer for protoc plugins.

This module provides Cargo integration for installing and managing Rust protoc plugins
like prost-build, tonic-build, and other Rust-based code generators.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any

from package_manager_base import (
    BasePackageManagerInstaller, 
    PluginSpec, 
    InstallationResult,
    PackageManagerUnavailableError
)
from package_manager_detector import PackageManagerInfo


class CargoPluginInstaller(BasePackageManagerInstaller):
    """Install and manage Rust protoc plugins via Cargo."""
    
    def __init__(self, cache_dir: str, verbose: bool = False):
        """
        Initialize the Cargo plugin installer.
        
        Args:
            cache_dir: Directory to store cached installations
            verbose: Enable verbose logging
        """
        super().__init__(cache_dir, verbose)
        
        # Rust plugin configuration database
        self.rust_plugins = {
            "prost-build": {
                "description": "Prost protobuf code generator for Rust",
                "crate": "prost-build",
                "binary": "protoc-gen-prost",
                "default_version": "0.12.3",
                "install_args": [],
                "features": [],
                "git_url": None,
            },
            "tonic-build": {
                "description": "Tonic gRPC code generator for Rust",
                "crate": "tonic-build", 
                "binary": "protoc-gen-tonic",
                "default_version": "0.10.2",
                "install_args": [],
                "features": [],
                "git_url": None,
            },
            "protobuf-codegen": {
                "description": "Rust protobuf code generator",
                "crate": "protobuf-codegen",
                "binary": "protoc-gen-rust",
                "default_version": "3.4.0",
                "install_args": [],
                "features": [],
                "git_url": None,
            },
            "protoc-gen-prost": {
                "description": "Standalone Prost protoc plugin",
                "crate": "protoc-gen-prost",
                "binary": "protoc-gen-prost",
                "default_version": "0.2.3",
                "install_args": [],
                "features": [],
                "git_url": None,
            },
            "protoc-gen-tonic": {
                "description": "Standalone Tonic protoc plugin",
                "crate": "protoc-gen-tonic",
                "binary": "protoc-gen-tonic",
                "default_version": "0.4.0",
                "install_args": [],
                "features": [],
                "git_url": None,
            },
            "buf-build-connect-rs": {
                "description": "Connect for Rust protoc plugin",
                "crate": "buf-build-connect-rs",
                "binary": "protoc-gen-connect-rs",
                "default_version": "0.1.0",
                "install_args": [],
                "features": [],
                "git_url": "https://github.com/bufbuild/connect-rust",
            },
        }
    
    def get_manager_name(self) -> str:
        """Get the name of the package manager."""
        return "cargo"
    
    def get_manager_info(self) -> PackageManagerInfo:
        """Get Cargo package manager information and availability."""
        return self.detector.detect_cargo()
    
    def get_supported_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of supported Rust plugins and their configurations."""
        return self.rust_plugins
    
    def get_cargo_home(self) -> Optional[Path]:
        """Get the Cargo home directory."""
        cargo_home = os.environ.get("CARGO_HOME")
        if cargo_home:
            return Path(cargo_home)
        
        # Default Cargo home
        home_dir = Path.home()
        return home_dir / ".cargo"
    
    def get_cargo_bin_dir(self) -> Optional[Path]:
        """Get the Cargo bin directory where installed binaries are placed."""
        cargo_home = self.get_cargo_home()
        if cargo_home:
            return cargo_home / "bin"
        return None
    
    def find_installed_binary(self, binary_name: str) -> Optional[Path]:
        """
        Find an installed Cargo binary.
        
        Args:
            binary_name: Name of the binary to find
            
        Returns:
            Path to the binary if found, None otherwise
        """
        # Check Cargo bin directory
        cargo_bin = self.get_cargo_bin_dir()
        if cargo_bin:
            binary_path = cargo_bin / binary_name
            if binary_path.exists() and binary_path.is_file():
                return binary_path
            
            # Check for .exe extension on Windows
            if os.name == "nt":
                binary_path_exe = cargo_bin / f"{binary_name}.exe"
                if binary_path_exe.exists() and binary_path_exe.is_file():
                    return binary_path_exe
        
        # Check PATH
        import shutil
        path_binary = shutil.which(binary_name)
        if path_binary:
            return Path(path_binary)
        
        return None
    
    def get_installed_crates(self) -> Dict[str, str]:
        """
        Get list of installed Cargo crates and their versions.
        
        Returns:
            Dictionary mapping crate names to versions
        """
        success, stdout, stderr = self.run_command_safely([
            "cargo", "install", "--list"
        ], timeout=30)
        
        if not success:
            self.log(f"Failed to list installed crates: {stderr}")
            return {}
        
        crates = {}
        current_crate = None
        
        for line in stdout.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Parse lines like "crate-name v1.2.3:"
            if line.endswith(':'):
                # Extract crate name and version
                parts = line[:-1].split()
                if len(parts) >= 2:
                    crate_name = parts[0]
                    version = parts[1].lstrip('v')
                    crates[crate_name] = version
                    current_crate = crate_name
        
        return crates
    
    def is_plugin_installed(self, plugin_spec: PluginSpec) -> Optional[Path]:
        """
        Check if a plugin is already installed via Cargo.
        
        Args:
            plugin_spec: Plugin specification
            
        Returns:
            Path to the installed binary if found, None otherwise
        """
        if plugin_spec.name not in self.rust_plugins:
            return None
        
        plugin_config = self.rust_plugins[plugin_spec.name]
        binary_name = plugin_config["binary"]
        
        # Check if binary is available
        binary_path = self.find_installed_binary(binary_name)
        if not binary_path:
            return None
        
        # Check if the crate is installed with the right version
        installed_crates = self.get_installed_crates()
        crate_name = plugin_config["crate"]
        
        if crate_name in installed_crates:
            installed_version = installed_crates[crate_name]
            if installed_version == plugin_spec.version:
                self.log(f"Plugin {plugin_spec.name} v{plugin_spec.version} already installed: {binary_path}")
                return binary_path
            else:
                self.log(f"Plugin {plugin_spec.name} installed but wrong version: {installed_version} != {plugin_spec.version}")
        
        return None
    
    def install_plugin_impl(self, plugin_spec: PluginSpec, install_dir: Path) -> InstallationResult:
        """
        Implementation-specific plugin installation using Cargo.
        
        Args:
            plugin_spec: Plugin specification
            install_dir: Directory to install the plugin (not used for Cargo global installs)
            
        Returns:
            InstallationResult with details of the installation
        """
        if plugin_spec.name not in self.rust_plugins:
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=f"Unsupported Rust plugin: {plugin_spec.name}",
                method="cargo"
            )
        
        plugin_config = self.rust_plugins[plugin_spec.name]
        crate_name = plugin_config["crate"]
        binary_name = plugin_config["binary"]
        
        self.log(f"Installing Rust plugin {plugin_spec.name} (crate: {crate_name})")
        
        # Check if already installed with correct version
        existing_binary = self.is_plugin_installed(plugin_spec)
        if existing_binary:
            # Create a symbolic link or wrapper in our cache directory
            wrapper_path = self.create_wrapper_script(
                install_dir, 
                binary_name, 
                str(existing_binary)
            )
            
            return InstallationResult(
                success=True,
                plugin_name=plugin_spec.name,
                binary_path=existing_binary,
                wrapper_path=wrapper_path,
                method="cargo_existing"
            )
        
        # Build cargo install command
        install_command = ["cargo", "install"]
        
        # Add version specification
        if plugin_spec.version:
            install_command.extend(["--version", plugin_spec.version])
        
        # Add features if specified
        features = plugin_config.get("features", [])
        if plugin_spec.install_args:
            # Parse install args for features
            for i, arg in enumerate(plugin_spec.install_args):
                if arg == "--features" and i + 1 < len(plugin_spec.install_args):
                    features.extend(plugin_spec.install_args[i + 1].split(','))
        
        if features:
            install_command.extend(["--features", ",".join(features)])
        
        # Add git URL if specified
        git_url = plugin_config.get("git_url")
        if git_url:
            install_command.extend(["--git", git_url])
        else:
            # Install from crates.io
            install_command.append(crate_name)
        
        # Add any additional install arguments
        install_args = plugin_config.get("install_args", [])
        if install_args:
            install_command.extend(install_args)
        
        # Add force flag to reinstall if different version
        install_command.append("--force")
        
        self.log(f"Running cargo install command: {' '.join(install_command)}")
        
        # Run cargo install
        success, stdout, stderr = self.run_command_safely(
            install_command,
            timeout=600  # 10 minutes for compilation
        )
        
        if not success:
            error_msg = f"Cargo install failed: {stderr}"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method="cargo"
            )
        
        # Find the installed binary
        binary_path = self.find_installed_binary(binary_name)
        if not binary_path:
            error_msg = f"Binary {binary_name} not found after installation"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method="cargo"
            )
        
        # Create a wrapper in our cache directory for consistency
        wrapper_path = self.create_wrapper_script(
            install_dir,
            binary_name,
            str(binary_path)
        )
        
        self.log(f"Successfully installed {plugin_spec.name} via Cargo: {binary_path}")
        
        return InstallationResult(
            success=True,
            plugin_name=plugin_spec.name,
            binary_path=binary_path,
            wrapper_path=wrapper_path,
            method="cargo"
        )
    
    def uninstall_plugin(self, plugin_name: str, version: str) -> bool:
        """
        Uninstall a plugin using cargo uninstall.
        
        Args:
            plugin_name: Name of the plugin
            version: Version of the plugin (ignored for cargo uninstall)
            
        Returns:
            True if successful, False otherwise
        """
        if plugin_name not in self.rust_plugins:
            self.log(f"Unknown plugin: {plugin_name}")
            return False
        
        plugin_config = self.rust_plugins[plugin_name]
        crate_name = plugin_config["crate"]
        
        self.log(f"Uninstalling Rust plugin {plugin_name} (crate: {crate_name})")
        
        # Run cargo uninstall
        success, stdout, stderr = self.run_command_safely([
            "cargo", "uninstall", crate_name
        ], timeout=60)
        
        if not success:
            self.log(f"Cargo uninstall failed: {stderr}")
            return False
        
        # Also remove our cache entry
        super().uninstall_plugin(plugin_name, version)
        
        self.log(f"Successfully uninstalled {plugin_name}")
        return True
    
    def update_plugin(self, plugin_name: str, version: Optional[str] = None) -> InstallationResult:
        """
        Update a plugin to a new version.
        
        Args:
            plugin_name: Name of the plugin
            version: Target version (latest if None)
            
        Returns:
            InstallationResult with details of the update
        """
        if plugin_name not in self.rust_plugins:
            return InstallationResult(
                success=False,
                plugin_name=plugin_name,
                error_message=f"Unsupported plugin: {plugin_name}",
                method="cargo"
            )
        
        plugin_config = self.rust_plugins[plugin_name]
        target_version = version or plugin_config["default_version"]
        
        # Create plugin spec for the target version
        plugin_spec = PluginSpec(
            name=plugin_name,
            version=target_version,
            binary_name=plugin_config["binary"]
        )
        
        # Install (which will update if needed due to --force flag)
        cache_key = f"{plugin_name}-{target_version}"
        install_dir = self.cache_dir / self.get_manager_name() / cache_key
        
        return self.install_plugin_impl(plugin_spec, install_dir)
    
    def list_available_plugins(self) -> List[Dict[str, Any]]:
        """
        List all available Rust plugins that can be installed.
        
        Returns:
            List of plugin information dictionaries
        """
        plugins = []
        for name, config in self.rust_plugins.items():
            plugins.append({
                "name": name,
                "crate": config["crate"],
                "binary": config["binary"],
                "description": config["description"],
                "default_version": config["default_version"],
                "git_url": config.get("git_url"),
                "manager": "cargo",
            })
        
        return plugins
    
    def search_crates(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for Rust crates related to protoc plugins.
        
        Args:
            query: Search query
            
        Returns:
            List of matching crates
        """
        self.log(f"Searching for Rust crates: {query}")
        
        # Use cargo search
        success, stdout, stderr = self.run_command_safely([
            "cargo", "search", query, "--limit", "10"
        ], timeout=30)
        
        if not success:
            self.log(f"Cargo search failed: {stderr}")
            return []
        
        crates = []
        for line in stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith('...'):
                continue
            
            # Parse lines like "crate-name = "1.2.3"    # Description"
            if '=' in line and '"' in line:
                try:
                    name_part, rest = line.split('=', 1)
                    name = name_part.strip()
                    
                    # Extract version
                    version_start = rest.find('"') + 1
                    version_end = rest.find('"', version_start)
                    version = rest[version_start:version_end] if version_end > version_start else ""
                    
                    # Extract description
                    description = ""
                    if '#' in rest:
                        description = rest.split('#', 1)[1].strip()
                    
                    crates.append({
                        "name": name,
                        "version": version,
                        "description": description,
                    })
                    
                except Exception as e:
                    self.log(f"Failed to parse cargo search line: {line} - {e}")
                    continue
        
        return crates


def main():
    """Main entry point for Cargo plugin installer testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cargo Plugin Installer")
    parser.add_argument("--plugin", help="Plugin name to install")
    parser.add_argument("--version", help="Plugin version")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall plugin")
    parser.add_argument("--update", action="store_true", help="Update plugin")
    parser.add_argument("--list-available", action="store_true", help="List available plugins")
    parser.add_argument("--list-installed", action="store_true", help="List installed plugins")
    parser.add_argument("--search", help="Search for plugins")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        # Initialize installer
        cache_dir = args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf")
        installer = CargoPluginInstaller(cache_dir, verbose=args.verbose)
        
        # Check if Cargo is available
        if not installer.is_available():
            print("ERROR: Cargo is not available", file=sys.stderr)
            sys.exit(1)
        
        if args.list_available:
            plugins = installer.list_available_plugins()
            print("Available Rust plugins:")
            for plugin in plugins:
                print(f"  {plugin['name']} ({plugin['crate']}) - {plugin['description']}")
            return
        
        if args.list_installed:
            plugins = installer.list_installed_plugins()
            print("Installed plugins:")
            for plugin in plugins:
                print(f"  {plugin['name']} v{plugin['version']} - {plugin['binary_path']}")
            return
        
        if args.search:
            crates = installer.search_crates(args.search)
            print(f"Search results for '{args.search}':")
            for crate in crates:
                print(f"  {crate['name']} v{crate['version']} - {crate['description']}")
            return
        
        if not args.plugin:
            parser.print_help()
            return
        
        if args.uninstall:
            success = installer.uninstall_plugin(args.plugin, args.version or "")
            if success:
                print(f"Successfully uninstalled {args.plugin}")
            else:
                print(f"Failed to uninstall {args.plugin}", file=sys.stderr)
                sys.exit(1)
        
        elif args.update:
            result = installer.update_plugin(args.plugin, args.version)
            if result.success:
                print(f"Successfully updated {args.plugin} to {args.version or 'latest'}")
                print(f"Binary: {result.binary_path}")
            else:
                print(f"Failed to update {args.plugin}: {result.error_message}", file=sys.stderr)
                sys.exit(1)
        
        else:
            # Install plugin
            if not args.version:
                supported_plugins = installer.get_supported_plugins()
                if args.plugin in supported_plugins:
                    args.version = supported_plugins[args.plugin]["default_version"]
                else:
                    print(f"ERROR: Version required for plugin {args.plugin}", file=sys.stderr)
                    sys.exit(1)
            
            plugin_spec = PluginSpec(
                name=args.plugin,
                version=args.version
            )
            
            result = installer.install_plugin(plugin_spec)
            if result.success:
                print(f"Successfully installed {args.plugin} v{args.version}")
                print(f"Binary: {result.binary_path}")
                if result.wrapper_path:
                    print(f"Wrapper: {result.wrapper_path}")
            else:
                print(f"Failed to install {args.plugin}: {result.error_message}", file=sys.stderr)
                sys.exit(1)
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
