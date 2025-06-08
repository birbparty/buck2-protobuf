#!/usr/bin/env python3
"""
NPM (Node.js) plugin installer for protoc plugins.

This module provides NPM/Yarn/pnpm integration for installing and managing TypeScript
protoc plugins like @protobuf-ts/plugin, protoc-gen-ts, ts-proto, and Connect-ES plugins.
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


class NPMPluginInstaller(BasePackageManagerInstaller):
    """Install and manage TypeScript protoc plugins via NPM/Yarn/pnpm."""
    
    def __init__(self, cache_dir: str, verbose: bool = False, prefer_manager: Optional[str] = None):
        """
        Initialize the NPM plugin installer.
        
        Args:
            cache_dir: Directory to store cached installations
            verbose: Enable verbose logging
            prefer_manager: Preferred package manager (npm, yarn, pnpm)
        """
        super().__init__(cache_dir, verbose)
        self.prefer_manager = prefer_manager
        self._selected_manager = None
        
        # TypeScript plugin configuration database
        self.typescript_plugins = {
            "protoc-gen-ts": {
                "description": "TypeScript protoc plugin",
                "package": "protoc-gen-ts",
                "binary": "protoc-gen-ts",
                "default_version": "0.8.7",
                "entry_point": "protoc-gen-ts",
                "install_args": [],
                "global_install": True,
            },
            "ts-proto": {
                "description": "TypeScript protoc plugin with modern APIs",
                "package": "ts-proto",
                "binary": "protoc-gen-ts-proto",
                "default_version": "2.7.2",
                "entry_point": "protoc-gen-ts-proto",
                "install_args": [],
                "global_install": True,
            },
            "protobuf-ts": {
                "description": "Protobuf-TS plugin for modern TypeScript",
                "package": "@protobuf-ts/plugin",
                "binary": "protoc-gen-ts",
                "default_version": "2.11.0",
                "entry_point": "protoc-gen-ts",
                "install_args": [],
                "global_install": True,
            },
            "protoc-gen-es": {
                "description": "Protobuf-ES plugin for ECMAScript",
                "package": "@bufbuild/protoc-gen-es",
                "binary": "protoc-gen-es",
                "default_version": "1.10.0",
                "entry_point": "protoc-gen-es",
                "install_args": [],
                "global_install": True,
            },
            "protoc-gen-connect-es": {
                "description": "Connect-ES plugin for TypeScript",
                "package": "@connectrpc/protoc-gen-connect-es",
                "binary": "protoc-gen-connect-es",
                "default_version": "1.6.1",
                "entry_point": "protoc-gen-connect-es",
                "install_args": [],
                "global_install": True,
            },
            "grpc-web-protoc-gen-ts": {
                "description": "gRPC-Web TypeScript plugin",
                "package": "grpc-web-protoc-gen-ts",
                "binary": "protoc-gen-grpc-web-ts",
                "default_version": "1.0.3",
                "entry_point": "protoc-gen-grpc-web-ts",
                "install_args": [],
                "global_install": True,
            },
            "protoc-gen-grpc-web": {
                "description": "gRPC-Web JavaScript/TypeScript plugin",
                "package": "grpc-web",
                "binary": "protoc-gen-grpc-web",
                "default_version": "1.5.0",
                "entry_point": "protoc-gen-grpc-web",
                "install_args": [],
                "global_install": True,
            },
        }
    
    def get_manager_name(self) -> str:
        """Get the name of the package manager."""
        selected = self.get_selected_manager()
        return selected.name if selected else "npm"
    
    def get_manager_info(self) -> PackageManagerInfo:
        """Get Node.js package manager information and availability."""
        return self.get_selected_manager()
    
    def get_selected_manager(self) -> PackageManagerInfo:
        """
        Get the selected Node.js package manager with preference order.
        
        Returns:
            PackageManagerInfo for the best available manager
        """
        if self._selected_manager:
            return self._selected_manager
        
        # If user specified a preference, try that first
        if self.prefer_manager:
            if self.prefer_manager == "npm":
                info = self.detector.detect_npm()
            elif self.prefer_manager == "yarn":
                info = self.detector.detect_yarn()
            elif self.prefer_manager == "pnpm":
                info = self.detector.detect_pnpm()
            else:
                info = self.detector.detect_npm()
            
            if info.available:
                self._selected_manager = info
                return info
        
        # Use default preference order: pnpm > yarn > npm
        preferred = self.detector.get_preferred_node_manager()
        if preferred:
            self._selected_manager = preferred
            return preferred
        
        # Fallback to npm (even if not available, for error reporting)
        self._selected_manager = self.detector.detect_npm()
        return self._selected_manager
    
    def get_supported_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of supported TypeScript plugins and their configurations."""
        return self.typescript_plugins
    
    def get_global_node_modules_bin(self) -> Optional[Path]:
        """Get the global node_modules/.bin directory."""
        manager = self.get_selected_manager()
        if not manager.available:
            return None
        
        try:
            if manager.name == "npm":
                # Get npm global bin directory
                success, stdout, stderr = self.run_command_safely([
                    manager.executable, "bin", "-g"
                ], timeout=10)
                if success and stdout:
                    return Path(stdout.strip())
            
            elif manager.name in ["yarn", "pnpm"]:
                # Get yarn/pnpm global bin directory
                success, stdout, stderr = self.run_command_safely([
                    manager.executable, "global", "bin"
                ], timeout=10)
                if success and stdout:
                    return Path(stdout.strip())
        
        except Exception as e:
            self.log(f"Failed to get global bin directory: {e}")
        
        return None
    
    def find_installed_binary(self, binary_name: str, package_name: str) -> Optional[Path]:
        """
        Find an installed Node.js binary.
        
        Args:
            binary_name: Name of the binary to find
            package_name: NPM package name
            
        Returns:
            Path to the binary if found, None otherwise
        """
        # Check global node_modules/.bin
        global_bin = self.get_global_node_modules_bin()
        if global_bin:
            binary_path = global_bin / binary_name
            if binary_path.exists() and binary_path.is_file():
                return binary_path
            
            # Check for .cmd/.bat extension on Windows
            if os.name == "nt":
                for ext in [".cmd", ".bat"]:
                    binary_path_ext = global_bin / f"{binary_name}{ext}"
                    if binary_path_ext.exists() and binary_path_ext.is_file():
                        return binary_path_ext
        
        # Check PATH
        import shutil
        path_binary = shutil.which(binary_name)
        if path_binary:
            return Path(path_binary)
        
        return None
    
    def get_installed_packages(self) -> Dict[str, str]:
        """
        Get list of globally installed packages and their versions.
        
        Returns:
            Dictionary mapping package names to versions
        """
        manager = self.get_selected_manager()
        if not manager.available:
            return {}
        
        try:
            if manager.name == "npm":
                success, stdout, stderr = self.run_command_safely([
                    manager.executable, "list", "-g", "--depth=0", "--json"
                ], timeout=30)
                
                if success and stdout:
                    data = json.loads(stdout)
                    dependencies = data.get("dependencies", {})
                    return {name: info.get("version", "") for name, info in dependencies.items()}
            
            elif manager.name == "yarn":
                success, stdout, stderr = self.run_command_safely([
                    manager.executable, "global", "list", "--json"
                ], timeout=30)
                
                if success and stdout:
                    packages = {}
                    for line in stdout.split('\n'):
                        try:
                            data = json.loads(line)
                            if data.get("type") == "info" and "data" in data:
                                # Parse yarn output format
                                data_str = data["data"]
                                if "@" in data_str and data_str.count("@") >= 2:
                                    # Format: @scope/package@version or package@version
                                    if data_str.startswith("@"):
                                        # Scoped package
                                        parts = data_str.rsplit("@", 1)
                                        if len(parts) == 2:
                                            packages[parts[0]] = parts[1]
                                    else:
                                        # Regular package
                                        parts = data_str.rsplit("@", 1)
                                        if len(parts) == 2:
                                            packages[parts[0]] = parts[1]
                        except json.JSONDecodeError:
                            continue
                    return packages
            
            elif manager.name == "pnpm":
                success, stdout, stderr = self.run_command_safely([
                    manager.executable, "list", "-g", "--depth=0", "--json"
                ], timeout=30)
                
                if success and stdout:
                    data = json.loads(stdout)
                    if isinstance(data, list) and len(data) > 0:
                        dependencies = data[0].get("dependencies", {})
                        return {name: info.get("version", "") for name, info in dependencies.items()}
        
        except Exception as e:
            self.log(f"Failed to list installed packages: {e}")
        
        return {}
    
    def is_plugin_installed(self, plugin_spec: PluginSpec) -> Optional[Path]:
        """
        Check if a plugin is already installed via package manager.
        
        Args:
            plugin_spec: Plugin specification
            
        Returns:
            Path to the installed binary if found, None otherwise
        """
        if plugin_spec.name not in self.typescript_plugins:
            return None
        
        plugin_config = self.typescript_plugins[plugin_spec.name]
        package_name = plugin_config["package"]
        binary_name = plugin_config["binary"]
        
        # Check if binary is available
        binary_path = self.find_installed_binary(binary_name, package_name)
        if not binary_path:
            return None
        
        # Check if the package is installed with the right version
        installed_packages = self.get_installed_packages()
        
        if package_name in installed_packages:
            installed_version = installed_packages[package_name]
            if installed_version == plugin_spec.version:
                self.log(f"Plugin {plugin_spec.name} v{plugin_spec.version} already installed: {binary_path}")
                return binary_path
            else:
                self.log(f"Plugin {plugin_spec.name} installed but wrong version: {installed_version} != {plugin_spec.version}")
        
        return None
    
    def create_local_package_json(self, install_dir: Path, plugins: List[PluginSpec]) -> Path:
        """
        Create a package.json for local plugin installation.
        
        Args:
            install_dir: Installation directory
            plugins: List of plugins to install
            
        Returns:
            Path to the created package.json
        """
        package_json_path = install_dir / "package.json"
        
        dependencies = {}
        for plugin in plugins:
            if plugin.name in self.typescript_plugins:
                plugin_config = self.typescript_plugins[plugin.name]
                package_name = plugin_config["package"]
                dependencies[package_name] = plugin.version
        
        package_data = {
            "name": "protoc-plugins-env",
            "version": "1.0.0",
            "description": "Local environment for protoc TypeScript plugins",
            "private": True,
            "dependencies": dependencies,
        }
        
        with open(package_json_path, 'w') as f:
            json.dump(package_data, f, indent=2)
        
        self.log(f"Created package.json: {package_json_path}")
        return package_json_path
    
    def install_plugin_impl(self, plugin_spec: PluginSpec, install_dir: Path) -> InstallationResult:
        """
        Implementation-specific plugin installation using NPM/Yarn/pnpm.
        
        Args:
            plugin_spec: Plugin specification
            install_dir: Directory to install the plugin
            
        Returns:
            InstallationResult with details of the installation
        """
        if plugin_spec.name not in self.typescript_plugins:
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=f"Unsupported TypeScript plugin: {plugin_spec.name}",
                method="npm"
            )
        
        plugin_config = self.typescript_plugins[plugin_spec.name]
        package_name = plugin_config["package"]
        binary_name = plugin_config["binary"]
        entry_point = plugin_config["entry_point"]
        global_install = plugin_config.get("global_install", True) and plugin_spec.global_install
        
        manager = self.get_selected_manager()
        self.log(f"Installing TypeScript plugin {plugin_spec.name} (package: {package_name}) using {manager.name}")
        
        # Check if already installed with correct version
        existing_binary = self.is_plugin_installed(plugin_spec)
        if existing_binary and global_install:
            # Create a wrapper in our cache directory for consistency
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
                method=f"{manager.name}_existing"
            )
        
        if global_install:
            # Global installation
            return self._install_global_plugin(plugin_spec, install_dir, manager, plugin_config)
        else:
            # Local installation
            return self._install_local_plugin(plugin_spec, install_dir, manager, plugin_config)
    
    def _install_global_plugin(self, plugin_spec: PluginSpec, install_dir: Path, 
                              manager: PackageManagerInfo, plugin_config: Dict[str, Any]) -> InstallationResult:
        """Install plugin globally."""
        package_name = plugin_config["package"]
        binary_name = plugin_config["binary"]
        
        # Build install command
        if manager.name == "npm":
            install_command = [manager.executable, "install", "-g", f"{package_name}@{plugin_spec.version}"]
        elif manager.name == "yarn":
            install_command = [manager.executable, "global", "add", f"{package_name}@{plugin_spec.version}"]
        elif manager.name == "pnpm":
            install_command = [manager.executable, "add", "-g", f"{package_name}@{plugin_spec.version}"]
        else:
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=f"Unsupported package manager: {manager.name}",
                method=manager.name
            )
        
        # Add any additional install arguments
        install_args = plugin_config.get("install_args", [])
        if install_args:
            install_command.extend(install_args)
        
        self.log(f"Running {manager.name} install command: {' '.join(install_command)}")
        
        # Run package manager install
        success, stdout, stderr = self.run_command_safely(
            install_command,
            timeout=300  # 5 minutes
        )
        
        if not success:
            error_msg = f"{manager.name} install failed: {stderr}"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method=manager.name
            )
        
        # Find the installed binary
        binary_path = self.find_installed_binary(binary_name, package_name)
        if not binary_path:
            error_msg = f"Binary {binary_name} not found after installation"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method=manager.name
            )
        
        # Create a wrapper in our cache directory for consistency
        wrapper_path = self.create_wrapper_script(
            install_dir,
            binary_name,
            str(binary_path)
        )
        
        self.log(f"Successfully installed {plugin_spec.name} globally via {manager.name}: {binary_path}")
        
        return InstallationResult(
            success=True,
            plugin_name=plugin_spec.name,
            binary_path=binary_path,
            wrapper_path=wrapper_path,
            method=manager.name
        )
    
    def _install_local_plugin(self, plugin_spec: PluginSpec, install_dir: Path, 
                             manager: PackageManagerInfo, plugin_config: Dict[str, Any]) -> InstallationResult:
        """Install plugin locally in project directory."""
        package_name = plugin_config["package"]
        binary_name = plugin_config["binary"]
        entry_point = plugin_config["entry_point"]
        
        # Create package.json
        package_json = self.create_local_package_json(install_dir, [plugin_spec])
        
        # Build install command
        if manager.name == "npm":
            install_command = [manager.executable, "install"]
        elif manager.name == "yarn":
            install_command = [manager.executable, "install"]
        elif manager.name == "pnpm":
            install_command = [manager.executable, "install"]
        else:
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=f"Unsupported package manager: {manager.name}",
                method=manager.name
            )
        
        self.log(f"Running {manager.name} install command: {' '.join(install_command)}")
        
        # Run package manager install
        success, stdout, stderr = self.run_command_safely(
            install_command,
            cwd=install_dir,
            timeout=300  # 5 minutes
        )
        
        if not success:
            error_msg = f"{manager.name} install failed: {stderr}"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method=manager.name
            )
        
        # Find the installed binary in node_modules/.bin
        node_modules_bin = install_dir / "node_modules" / ".bin"
        binary_path = node_modules_bin / binary_name
        
        if not binary_path.exists():
            # Try with common extensions on Windows
            if os.name == "nt":
                for ext in [".cmd", ".bat", ".ps1"]:
                    binary_path_ext = node_modules_bin / f"{binary_name}{ext}"
                    if binary_path_ext.exists():
                        binary_path = binary_path_ext
                        break
        
        if not binary_path.exists():
            error_msg = f"Binary {binary_name} not found in node_modules/.bin after installation"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method=manager.name
            )
        
        # Create a wrapper script that references the local installation
        wrapper_path = self.create_wrapper_script(
            install_dir,
            binary_name,
            str(binary_path)
        )
        
        self.log(f"Successfully installed {plugin_spec.name} locally via {manager.name}: {binary_path}")
        
        return InstallationResult(
            success=True,
            plugin_name=plugin_spec.name,
            binary_path=binary_path,
            wrapper_path=wrapper_path,
            method=f"{manager.name}_local"
        )
    
    def uninstall_plugin(self, plugin_name: str, version: str) -> bool:
        """
        Uninstall a plugin using package manager uninstall.
        
        Args:
            plugin_name: Name of the plugin
            version: Version of the plugin
            
        Returns:
            True if successful, False otherwise
        """
        if plugin_name not in self.typescript_plugins:
            self.log(f"Unknown plugin: {plugin_name}")
            return False
        
        plugin_config = self.typescript_plugins[plugin_name]
        package_name = plugin_config["package"]
        
        manager = self.get_selected_manager()
        self.log(f"Uninstalling TypeScript plugin {plugin_name} (package: {package_name}) using {manager.name}")
        
        # Build uninstall command
        if manager.name == "npm":
            uninstall_command = [manager.executable, "uninstall", "-g", package_name]
        elif manager.name == "yarn":
            uninstall_command = [manager.executable, "global", "remove", package_name]
        elif manager.name == "pnpm":
            uninstall_command = [manager.executable, "remove", "-g", package_name]
        else:
            self.log(f"Unsupported package manager: {manager.name}")
            return False
        
        # Run package manager uninstall
        success, stdout, stderr = self.run_command_safely(
            uninstall_command,
            timeout=60
        )
        
        if not success:
            self.log(f"{manager.name} uninstall failed: {stderr}")
            return False
        
        # Also remove our cache entry
        super().uninstall_plugin(plugin_name, version)
        
        self.log(f"Successfully uninstalled {plugin_name}")
        return True
    
    def list_available_plugins(self) -> List[Dict[str, Any]]:
        """
        List all available TypeScript plugins that can be installed.
        
        Returns:
            List of plugin information dictionaries
        """
        plugins = []
        for name, config in self.typescript_plugins.items():
            plugins.append({
                "name": name,
                "package": config["package"],
                "binary": config["binary"],
                "description": config["description"],
                "default_version": config["default_version"],
                "entry_point": config["entry_point"],
                "manager": self.get_manager_name(),
            })
        
        return plugins
    
    def search_packages(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for npm packages related to protoc plugins.
        
        Args:
            query: Search query
            
        Returns:
            List of matching packages
        """
        manager = self.get_selected_manager()
        self.log(f"Searching for npm packages: {query}")
        
        # Use npm search (works for all package managers)
        success, stdout, stderr = self.run_command_safely([
            "npm", "search", query, "--json"
        ], timeout=30)
        
        if not success:
            self.log(f"npm search failed: {stderr}")
            return []
        
        try:
            results = json.loads(stdout)
            packages = []
            
            for result in results[:10]:  # Limit to 10 results
                packages.append({
                    "name": result.get("name", ""),
                    "version": result.get("version", ""),
                    "description": result.get("description", ""),
                    "keywords": result.get("keywords", []),
                    "author": result.get("author", {}).get("name", "") if result.get("author") else "",
                })
            
            return packages
            
        except json.JSONDecodeError as e:
            self.log(f"Failed to parse npm search results: {e}")
            return []


def main():
    """Main entry point for NPM plugin installer testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NPM Plugin Installer")
    parser.add_argument("--plugin", help="Plugin name to install")
    parser.add_argument("--version", help="Plugin version")
    parser.add_argument("--cache-dir", help="Cache directory")
    parser.add_argument("--manager", choices=["npm", "yarn", "pnpm"], help="Preferred package manager")
    parser.add_argument("--local", action="store_true", help="Install locally instead of globally")
    parser.add_argument("--uninstall", action="store_true", help="Uninstall plugin")
    parser.add_argument("--list-available", action="store_true", help="List available plugins")
    parser.add_argument("--list-installed", action="store_true", help="List installed plugins")
    parser.add_argument("--search", help="Search for plugins")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    try:
        # Initialize installer
        cache_dir = args.cache_dir or os.path.expanduser("~/.cache/buck2-protobuf")
        installer = NPMPluginInstaller(cache_dir, verbose=args.verbose, prefer_manager=args.manager)
        
        # Check if package manager is available
        if not installer.is_available():
            manager_name = installer.get_manager_name()
            print(f"ERROR: {manager_name} is not available", file=sys.stderr)
            sys.exit(1)
        
        if args.list_available:
            plugins = installer.list_available_plugins()
            print("Available TypeScript plugins:")
            for plugin in plugins:
                print(f"  {plugin['name']} ({plugin['package']}) - {plugin['description']}")
            return
        
        if args.list_installed:
            plugins = installer.list_installed_plugins()
            print("Installed plugins:")
            for plugin in plugins:
                print(f"  {plugin['name']} v{plugin['version']} - {plugin['binary_path']}")
            return
        
        if args.search:
            packages = installer.search_packages(args.search)
            print(f"Search results for '{args.search}':")
            for package in packages:
                print(f"  {package['name']} v{package['version']} - {package['description']}")
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
                version=args.version,
                global_install=not args.local
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
