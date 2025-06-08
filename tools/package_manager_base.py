#!/usr/bin/env python3
"""
Base classes for package manager plugin installers.

This module provides abstract base classes and common patterns for package manager
integrations, with standardized error handling and fallback mechanisms.
"""

import os
import sys
import tempfile
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from package_manager_detector import PackageManagerDetector, PackageManagerInfo


@dataclass
class PluginSpec:
    """Specification for a plugin installation."""
    name: str
    version: str
    package: Optional[str] = None  # Package name if different from plugin name
    install_args: Optional[List[str]] = None
    binary_name: Optional[str] = None  # Binary name if different from plugin name
    entry_point: Optional[str] = None  # Entry point for script-based plugins
    global_install: bool = True  # Whether to install globally
    optional: bool = False  # Whether plugin is optional


@dataclass
class InstallationResult:
    """Result of a plugin installation."""
    success: bool
    plugin_name: str
    binary_path: Optional[Path] = None
    wrapper_path: Optional[Path] = None
    error_message: Optional[str] = None
    installation_time: float = 0.0
    method: Optional[str] = None  # e.g., "package_manager", "oras", "http"


class PackageManagerUnavailableError(Exception):
    """Exception raised when package manager is not available."""
    pass


class PluginInstallationError(Exception):
    """Exception raised when plugin installation fails."""
    pass


class BasePackageManagerInstaller(ABC):
    """Abstract base class for package manager plugin installers."""
    
    def __init__(self, cache_dir: str, verbose: bool = False):
        """
        Initialize the package manager installer.
        
        Args:
            cache_dir: Directory to store cached installations
            verbose: Enable verbose logging
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.detector = PackageManagerDetector(verbose=verbose)
        
        # Installation metrics
        self.metrics = {
            "total_installs": 0,
            "successful_installs": 0,
            "failed_installs": 0,
            "cache_hits": 0,
            "avg_install_time": 0.0,
        }
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[{self.get_manager_name()}] {message}", file=sys.stderr)
    
    @abstractmethod
    def get_manager_name(self) -> str:
        """Get the name of the package manager (e.g., "cargo", "npm")."""
        pass
    
    @abstractmethod
    def get_manager_info(self) -> PackageManagerInfo:
        """Get package manager information and availability."""
        pass
    
    @abstractmethod
    def get_supported_plugins(self) -> Dict[str, Dict[str, Any]]:
        """Get dictionary of supported plugins and their configurations."""
        pass
    
    def run_command_safely(self, command: List[str], cwd: Optional[Path] = None, 
                          timeout: int = 300, env: Optional[Dict[str, str]] = None) -> Tuple[bool, str, str]:
        """
        Run a command safely with timeout and capture output.
        
        Args:
            command: Command and arguments as a list
            cwd: Working directory for the command
            timeout: Timeout in seconds
            env: Environment variables
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            self.log(f"Running command: {' '.join(command)}")
            if cwd:
                self.log(f"Working directory: {cwd}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                env=env,
                check=False
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if success:
                self.log(f"Command succeeded")
                if stdout and self.verbose:
                    self.log(f"stdout: {stdout}")
            else:
                self.log(f"Command failed with return code {result.returncode}")
                if stderr:
                    self.log(f"stderr: {stderr}")
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out after {timeout} seconds")
            return False, "", "Command timed out"
        except Exception as e:
            self.log(f"Error running command: {e}")
            return False, "", str(e)
    
    def is_available(self) -> bool:
        """Check if the package manager is available."""
        manager_info = self.get_manager_info()
        return manager_info.available
    
    def check_plugin_cached(self, plugin_spec: PluginSpec) -> Optional[Path]:
        """
        Check if plugin is already cached and return path to binary.
        
        Args:
            plugin_spec: Plugin specification
            
        Returns:
            Path to cached binary if available, None otherwise
        """
        cache_key = f"{plugin_spec.name}-{plugin_spec.version}"
        cached_dir = self.cache_dir / self.get_manager_name() / cache_key
        
        # Check for binary or wrapper
        for potential_name in [plugin_spec.binary_name, plugin_spec.name]:
            if not potential_name:
                continue
                
            # Check for direct binary
            binary_path = cached_dir / potential_name
            if binary_path.exists() and binary_path.is_file():
                if os.access(binary_path, os.X_OK):
                    self.log(f"Found cached binary: {binary_path}")
                    self.metrics["cache_hits"] += 1
                    return binary_path
            
            # Check for wrapper script
            wrapper_path = cached_dir / "bin" / potential_name
            if wrapper_path.exists() and wrapper_path.is_file():
                if os.access(wrapper_path, os.X_OK):
                    self.log(f"Found cached wrapper: {wrapper_path}")
                    self.metrics["cache_hits"] += 1
                    return wrapper_path
        
        return None
    
    def create_wrapper_script(self, install_dir: Path, binary_name: str, 
                             target_executable: str, args: Optional[List[str]] = None) -> Path:
        """
        Create a wrapper script for a plugin binary.
        
        Args:
            install_dir: Installation directory
            binary_name: Name of the wrapper binary
            target_executable: Path to the target executable
            args: Additional arguments to pass
            
        Returns:
            Path to the created wrapper script
        """
        wrapper_dir = install_dir / "bin"
        wrapper_dir.mkdir(parents=True, exist_ok=True)
        
        wrapper_path = wrapper_dir / binary_name
        args_str = " ".join(args) if args else ""
        
        if os.name == "nt":  # Windows
            wrapper_content = f"""@echo off
"{target_executable}" {args_str} %*
"""
        else:
            wrapper_content = f"""#!/bin/bash
exec "{target_executable}" {args_str} "$@"
"""
        
        with open(wrapper_path, 'w') as f:
            f.write(wrapper_content)
        
        wrapper_path.chmod(0o755)
        self.log(f"Created wrapper script: {wrapper_path}")
        
        return wrapper_path
    
    def validate_installation(self, binary_path: Path, plugin_name: str) -> bool:
        """
        Validate that a plugin installation is functional.
        
        Args:
            binary_path: Path to the plugin binary
            plugin_name: Name of the plugin
            
        Returns:
            True if installation is valid, False otherwise
        """
        if not binary_path.exists():
            self.log(f"Binary not found: {binary_path}")
            return False
        
        if not binary_path.is_file():
            self.log(f"Not a file: {binary_path}")
            return False
        
        if not os.access(binary_path, os.X_OK):
            self.log(f"Not executable: {binary_path}")
            return False
        
        # Try to run the binary with --help or --version
        for flag in ["--help", "--version", "-h", "-v"]:
            success, stdout, stderr = self.run_command_safely(
                [str(binary_path), flag], 
                timeout=10
            )
            # Most protoc plugins will exit with non-zero for --help but shouldn't crash
            if success or (not success and not "not found" in stderr.lower()):
                self.log(f"Plugin {plugin_name} validation passed")
                return True
        
        # If no flags work, just check that it can be executed
        success, stdout, stderr = self.run_command_safely([str(binary_path)], timeout=5)
        # Plugins typically exit with error when called without protoc, that's expected
        if "not found" not in stderr.lower() and "no such file" not in stderr.lower():
            self.log(f"Plugin {plugin_name} validation passed (basic execution)")
            return True
        
        self.log(f"Plugin {plugin_name} validation failed")
        return False
    
    @abstractmethod
    def install_plugin_impl(self, plugin_spec: PluginSpec, install_dir: Path) -> InstallationResult:
        """
        Implementation-specific plugin installation.
        
        Args:
            plugin_spec: Plugin specification
            install_dir: Directory to install the plugin
            
        Returns:
            InstallationResult with details of the installation
        """
        pass
    
    def install_plugin(self, plugin_spec: PluginSpec) -> InstallationResult:
        """
        Install a plugin using the package manager.
        
        Args:
            plugin_spec: Plugin specification
            
        Returns:
            InstallationResult with details of the installation
        """
        start_time = time.time()
        self.metrics["total_installs"] += 1
        
        self.log(f"Installing plugin {plugin_spec.name} version {plugin_spec.version}")
        
        # Check if package manager is available
        if not self.is_available():
            error_msg = f"{self.get_manager_name()} is not available"
            self.log(error_msg)
            self.metrics["failed_installs"] += 1
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                installation_time=time.time() - start_time,
                method="package_manager"
            )
        
        # Check if plugin is supported
        supported_plugins = self.get_supported_plugins()
        if plugin_spec.name not in supported_plugins:
            error_msg = f"Plugin {plugin_spec.name} is not supported by {self.get_manager_name()}"
            self.log(error_msg)
            self.metrics["failed_installs"] += 1
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                installation_time=time.time() - start_time,
                method="package_manager"
            )
        
        # Check cache first
        cached_path = self.check_plugin_cached(plugin_spec)
        if cached_path:
            self.log(f"Using cached plugin: {cached_path}")
            return InstallationResult(
                success=True,
                plugin_name=plugin_spec.name,
                binary_path=cached_path,
                installation_time=time.time() - start_time,
                method="cache"
            )
        
        # Prepare installation directory
        cache_key = f"{plugin_spec.name}-{plugin_spec.version}"
        install_dir = self.cache_dir / self.get_manager_name() / cache_key
        
        try:
            # Clean up any previous failed installation
            if install_dir.exists():
                shutil.rmtree(install_dir)
            
            install_dir.mkdir(parents=True, exist_ok=True)
            
            # Perform the actual installation
            result = self.install_plugin_impl(plugin_spec, install_dir)
            result.installation_time = time.time() - start_time
            
            # Update metrics
            if result.success:
                self.metrics["successful_installs"] += 1
                
                # Validate installation
                binary_path = result.binary_path or result.wrapper_path
                if binary_path and not self.validate_installation(binary_path, plugin_spec.name):
                    result.success = False
                    result.error_message = "Installation validation failed"
                    self.metrics["successful_installs"] -= 1
                    self.metrics["failed_installs"] += 1
            else:
                self.metrics["failed_installs"] += 1
            
            # Update average installation time
            total_successful = self.metrics["successful_installs"]
            if total_successful > 0:
                self.metrics["avg_install_time"] = (
                    self.metrics["avg_install_time"] * (total_successful - 1) + result.installation_time
                ) / total_successful
            
            return result
            
        except Exception as e:
            error_msg = f"Installation failed: {e}"
            self.log(error_msg)
            self.metrics["failed_installs"] += 1
            
            # Clean up on failure
            if install_dir.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
            
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                installation_time=time.time() - start_time,
                method="package_manager"
            )
    
    def uninstall_plugin(self, plugin_name: str, version: str) -> bool:
        """
        Uninstall a plugin (remove from cache).
        
        Args:
            plugin_name: Name of the plugin
            version: Version of the plugin
            
        Returns:
            True if successful, False otherwise
        """
        cache_key = f"{plugin_name}-{version}"
        install_dir = self.cache_dir / self.get_manager_name() / cache_key
        
        if install_dir.exists():
            try:
                shutil.rmtree(install_dir)
                self.log(f"Uninstalled plugin {plugin_name} version {version}")
                return True
            except Exception as e:
                self.log(f"Failed to uninstall plugin {plugin_name}: {e}")
                return False
        else:
            self.log(f"Plugin {plugin_name} version {version} not found in cache")
            return False
    
    def list_installed_plugins(self) -> List[Dict[str, Any]]:
        """
        List all installed plugins.
        
        Returns:
            List of dictionaries with plugin information
        """
        plugins = []
        manager_cache_dir = self.cache_dir / self.get_manager_name()
        
        if not manager_cache_dir.exists():
            return plugins
        
        for item in manager_cache_dir.iterdir():
            if item.is_dir():
                # Parse cache key (plugin-name-version)
                parts = item.name.rsplit('-', 1)
                if len(parts) == 2:
                    plugin_name, version = parts
                    
                    # Find binary or wrapper
                    binary_path = None
                    for potential_path in [
                        item / plugin_name,
                        item / "bin" / plugin_name,
                        item / f"protoc-gen-{plugin_name}",
                        item / "bin" / f"protoc-gen-{plugin_name}",
                    ]:
                        if potential_path.exists() and potential_path.is_file():
                            binary_path = potential_path
                            break
                    
                    plugins.append({
                        "name": plugin_name,
                        "version": version,
                        "binary_path": str(binary_path) if binary_path else None,
                        "install_dir": str(item),
                        "manager": self.get_manager_name(),
                    })
        
        return plugins
    
    def clear_cache(self, older_than_days: Optional[int] = None) -> int:
        """
        Clear cached plugins.
        
        Args:
            older_than_days: Only clear items older than this many days
            
        Returns:
            Number of items cleared
        """
        cleared_count = 0
        manager_cache_dir = self.cache_dir / self.get_manager_name()
        
        if not manager_cache_dir.exists():
            return cleared_count
        
        cutoff_time = time.time() - (older_than_days * 86400) if older_than_days else 0
        
        for item in manager_cache_dir.iterdir():
            if item.is_dir():
                if not older_than_days or item.stat().st_mtime < cutoff_time:
                    try:
                        shutil.rmtree(item)
                        cleared_count += 1
                        self.log(f"Cleared cache item: {item.name}")
                    except Exception as e:
                        self.log(f"Failed to clear cache item {item.name}: {e}")
        
        return cleared_count
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get installation metrics."""
        return self.metrics.copy()


class PackageManagerWrapper:
    """Wrapper for multiple package manager installers with fallback support."""
    
    def __init__(self, installers: List[BasePackageManagerInstaller], verbose: bool = False):
        """
        Initialize the package manager wrapper.
        
        Args:
            installers: List of package manager installers
            verbose: Enable verbose logging
        """
        self.installers = installers
        self.verbose = verbose
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[package-manager-wrapper] {message}", file=sys.stderr)
    
    def find_installer_for_plugin(self, plugin_name: str) -> Optional[BasePackageManagerInstaller]:
        """
        Find the best installer for a given plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Best available installer for the plugin, or None
        """
        for installer in self.installers:
            if installer.is_available():
                supported_plugins = installer.get_supported_plugins()
                if plugin_name in supported_plugins:
                    self.log(f"Found installer {installer.get_manager_name()} for plugin {plugin_name}")
                    return installer
        
        return None
    
    def install_plugin(self, plugin_spec: PluginSpec) -> InstallationResult:
        """
        Install a plugin using the best available package manager.
        
        Args:
            plugin_spec: Plugin specification
            
        Returns:
            InstallationResult from the installation attempt
        """
        installer = self.find_installer_for_plugin(plugin_spec.name)
        if installer:
            return installer.install_plugin(plugin_spec)
        else:
            error_msg = f"No package manager available for plugin {plugin_spec.name}"
            self.log(error_msg)
            return InstallationResult(
                success=False,
                plugin_name=plugin_spec.name,
                error_message=error_msg,
                method="no_manager"
            )
