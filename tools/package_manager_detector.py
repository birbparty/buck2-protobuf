#!/usr/bin/env python3
"""
Package manager detection and availability checking for cross-platform development.

This module provides cross-platform detection for Cargo, NPM, and other package managers,
with version checking and compatibility validation.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class PackageManagerInfo:
    """Information about a detected package manager."""
    name: str
    executable: str
    version: str
    available: bool
    install_path: Optional[Path] = None
    global_install_supported: bool = True
    local_install_supported: bool = True


class PackageManagerDetector:
    """Detect and validate package managers across platforms."""
    
    def __init__(self, verbose: bool = False):
        """
        Initialize the package manager detector.
        
        Args:
            verbose: Enable verbose logging
        """
        self.verbose = verbose
        self._cache = {}
    
    def log(self, message: str) -> None:
        """Log a message if verbose mode is enabled."""
        if self.verbose:
            print(f"[package-manager-detector] {message}", file=sys.stderr)
    
    def _run_command_safely(self, command: List[str], timeout: int = 10) -> Tuple[bool, str, str]:
        """
        Run a command safely with timeout and capture output.
        
        Args:
            command: Command and arguments as a list
            timeout: Timeout in seconds
            
        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            self.log(f"Running command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False
            )
            
            success = result.returncode == 0
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            
            if success:
                self.log(f"Command succeeded: {stdout}")
            else:
                self.log(f"Command failed (code {result.returncode}): {stderr}")
            
            return success, stdout, stderr
            
        except subprocess.TimeoutExpired:
            self.log(f"Command timed out after {timeout} seconds")
            return False, "", "Command timed out"
        except FileNotFoundError:
            self.log(f"Command not found: {command[0]}")
            return False, "", "Command not found"
        except Exception as e:
            self.log(f"Error running command: {e}")
            return False, "", str(e)
    
    def detect_cargo(self) -> PackageManagerInfo:
        """
        Detect Cargo (Rust package manager).
        
        Returns:
            PackageManagerInfo for Cargo
        """
        if "cargo" in self._cache:
            return self._cache["cargo"]
        
        self.log("Detecting Cargo...")
        
        # Try to find cargo executable
        cargo_path = shutil.which("cargo")
        if not cargo_path:
            result = PackageManagerInfo(
                name="cargo",
                executable="cargo",
                version="",
                available=False
            )
            self._cache["cargo"] = result
            return result
        
        # Get cargo version
        success, stdout, stderr = self._run_command_safely(["cargo", "--version"])
        if not success:
            result = PackageManagerInfo(
                name="cargo",
                executable="cargo",
                version="",
                available=False
            )
            self._cache["cargo"] = result
            return result
        
        # Parse version from output (e.g., "cargo 1.75.0 (1d8b05cdd 2023-11-20)")
        try:
            version = stdout.split()[1]
            self.log(f"Detected Cargo version: {version}")
        except (IndexError, ValueError):
            version = "unknown"
        
        # Check cargo install capability
        success, _, _ = self._run_command_safely(["cargo", "install", "--help"])
        install_supported = success
        
        result = PackageManagerInfo(
            name="cargo",
            executable="cargo",
            version=version,
            available=True,
            install_path=Path(cargo_path).parent,
            global_install_supported=install_supported,
            local_install_supported=False  # Cargo doesn't support local-only installs
        )
        
        self._cache["cargo"] = result
        return result
    
    def detect_npm(self) -> PackageManagerInfo:
        """
        Detect NPM (Node.js package manager).
        
        Returns:
            PackageManagerInfo for NPM
        """
        if "npm" in self._cache:
            return self._cache["npm"]
        
        self.log("Detecting NPM...")
        
        # Try to find npm executable
        npm_path = shutil.which("npm")
        if not npm_path:
            result = PackageManagerInfo(
                name="npm",
                executable="npm",
                version="",
                available=False
            )
            self._cache["npm"] = result
            return result
        
        # Get npm version
        success, stdout, stderr = self._run_command_safely(["npm", "--version"])
        if not success:
            result = PackageManagerInfo(
                name="npm",
                executable="npm",
                version="",
                available=False
            )
            self._cache["npm"] = result
            return result
        
        version = stdout.strip()
        self.log(f"Detected NPM version: {version}")
        
        # Check global and local install capabilities
        success_global, _, _ = self._run_command_safely(["npm", "install", "--help"])
        success_local, _, _ = self._run_command_safely(["npm", "install", "--help"])
        
        result = PackageManagerInfo(
            name="npm",
            executable="npm",
            version=version,
            available=True,
            install_path=Path(npm_path).parent,
            global_install_supported=success_global,
            local_install_supported=success_local
        )
        
        self._cache["npm"] = result
        return result
    
    def detect_yarn(self) -> PackageManagerInfo:
        """
        Detect Yarn (alternative Node.js package manager).
        
        Returns:
            PackageManagerInfo for Yarn
        """
        if "yarn" in self._cache:
            return self._cache["yarn"]
        
        self.log("Detecting Yarn...")
        
        # Try to find yarn executable
        yarn_path = shutil.which("yarn")
        if not yarn_path:
            result = PackageManagerInfo(
                name="yarn",
                executable="yarn",
                version="",
                available=False
            )
            self._cache["yarn"] = result
            return result
        
        # Get yarn version
        success, stdout, stderr = self._run_command_safely(["yarn", "--version"])
        if not success:
            result = PackageManagerInfo(
                name="yarn",
                executable="yarn",
                version="",
                available=False
            )
            self._cache["yarn"] = result
            return result
        
        version = stdout.strip()
        self.log(f"Detected Yarn version: {version}")
        
        result = PackageManagerInfo(
            name="yarn",
            executable="yarn",
            version=version,
            available=True,
            install_path=Path(yarn_path).parent,
            global_install_supported=True,
            local_install_supported=True
        )
        
        self._cache["yarn"] = result
        return result
    
    def detect_pnpm(self) -> PackageManagerInfo:
        """
        Detect pnpm (fast Node.js package manager).
        
        Returns:
            PackageManagerInfo for pnpm
        """
        if "pnpm" in self._cache:
            return self._cache["pnpm"]
        
        self.log("Detecting pnpm...")
        
        # Try to find pnpm executable
        pnpm_path = shutil.which("pnpm")
        if not pnpm_path:
            result = PackageManagerInfo(
                name="pnpm",
                executable="pnpm",
                version="",
                available=False
            )
            self._cache["pnpm"] = result
            return result
        
        # Get pnpm version
        success, stdout, stderr = self._run_command_safely(["pnpm", "--version"])
        if not success:
            result = PackageManagerInfo(
                name="pnpm",
                executable="pnpm",
                version="",
                available=False
            )
            self._cache["pnpm"] = result
            return result
        
        version = stdout.strip()
        self.log(f"Detected pnpm version: {version}")
        
        result = PackageManagerInfo(
            name="pnpm",
            executable="pnpm",
            version=version,
            available=True,
            install_path=Path(pnpm_path).parent,
            global_install_supported=True,
            local_install_supported=True
        )
        
        self._cache["pnpm"] = result
        return result
    
    def detect_pip(self) -> PackageManagerInfo:
        """
        Detect pip (Python package manager).
        
        Returns:
            PackageManagerInfo for pip
        """
        if "pip" in self._cache:
            return self._cache["pip"]
        
        self.log("Detecting pip...")
        
        # Try multiple pip variants
        pip_candidates = ["pip", "pip3", "python -m pip", "python3 -m pip"]
        
        for candidate in pip_candidates:
            if candidate.startswith("python"):
                # Handle module execution
                parts = candidate.split()
                success, stdout, stderr = self._run_command_safely(parts + ["--version"])
            else:
                pip_path = shutil.which(candidate)
                if not pip_path:
                    continue
                success, stdout, stderr = self._run_command_safely([candidate, "--version"])
            
            if success and "pip" in stdout:
                # Parse version from output (e.g., "pip 23.3.1 from ...")
                try:
                    version = stdout.split()[1]
                    self.log(f"Detected pip version: {version}")
                    
                    result = PackageManagerInfo(
                        name="pip",
                        executable=candidate,
                        version=version,
                        available=True,
                        install_path=Path(pip_path).parent if not candidate.startswith("python") else None,
                        global_install_supported=True,
                        local_install_supported=True  # via virtualenv
                    )
                    
                    self._cache["pip"] = result
                    return result
                    
                except (IndexError, ValueError):
                    continue
        
        # No pip found
        result = PackageManagerInfo(
            name="pip",
            executable="pip",
            version="",
            available=False
        )
        self._cache["pip"] = result
        return result
    
    def detect_all(self) -> Dict[str, PackageManagerInfo]:
        """
        Detect all supported package managers.
        
        Returns:
            Dictionary mapping package manager names to their info
        """
        self.log("Detecting all package managers...")
        
        managers = {
            "cargo": self.detect_cargo(),
            "npm": self.detect_npm(),
            "yarn": self.detect_yarn(),
            "pnpm": self.detect_pnpm(),
            "pip": self.detect_pip(),
        }
        
        available_count = sum(1 for info in managers.values() if info.available)
        self.log(f"Detected {available_count}/{len(managers)} package managers")
        
        return managers
    
    def get_preferred_node_manager(self) -> Optional[PackageManagerInfo]:
        """
        Get the preferred Node.js package manager (preference: pnpm > yarn > npm).
        
        Returns:
            PackageManagerInfo for the preferred manager, or None if none available
        """
        # Check in order of preference
        for manager_name in ["pnpm", "yarn", "npm"]:
            if manager_name == "pnpm":
                info = self.detect_pnpm()
            elif manager_name == "yarn":
                info = self.detect_yarn()
            else:
                info = self.detect_npm()
            
            if info.available:
                self.log(f"Using preferred Node.js package manager: {manager_name}")
                return info
        
        return None
    
    def check_compatibility(self, manager_name: str, min_version: Optional[str] = None) -> bool:
        """
        Check if a package manager meets minimum version requirements.
        
        Args:
            manager_name: Name of the package manager
            min_version: Minimum required version (semantic version string)
            
        Returns:
            True if compatible, False otherwise
        """
        if manager_name == "cargo":
            info = self.detect_cargo()
        elif manager_name == "npm":
            info = self.detect_npm()
        elif manager_name == "yarn":
            info = self.detect_yarn()
        elif manager_name == "pnpm":
            info = self.detect_pnpm()
        elif manager_name == "pip":
            info = self.detect_pip()
        else:
            return False
        
        if not info.available:
            return False
        
        if min_version is None:
            return True
        
        # Simple version comparison (for more complex needs, use packaging library)
        try:
            from packaging import version
            return version.parse(info.version) >= version.parse(min_version)
        except ImportError:
            # Fallback to string comparison if packaging not available
            self.log("Warning: packaging library not available, using string comparison")
            return info.version >= min_version
    
    def clear_cache(self) -> None:
        """Clear the detection cache."""
        self._cache.clear()
        self.log("Detection cache cleared")


def main():
    """Main entry point for package manager detection."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Detect package managers")
    parser.add_argument("--manager", help="Specific manager to detect (cargo, npm, yarn, pnpm, pip)")
    parser.add_argument("--min-version", help="Minimum version requirement")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    detector = PackageManagerDetector(verbose=args.verbose)
    
    if args.manager:
        # Detect specific manager
        if args.manager == "cargo":
            info = detector.detect_cargo()
        elif args.manager == "npm":
            info = detector.detect_npm()
        elif args.manager == "yarn":
            info = detector.detect_yarn()
        elif args.manager == "pnpm":
            info = detector.detect_pnpm()
        elif args.manager == "pip":
            info = detector.detect_pip()
        else:
            print(f"ERROR: Unknown package manager: {args.manager}", file=sys.stderr)
            sys.exit(1)
        
        # Check compatibility if min version specified
        if args.min_version:
            compatible = detector.check_compatibility(args.manager, args.min_version)
            if not compatible:
                print(f"ERROR: {args.manager} version {info.version} does not meet minimum requirement {args.min_version}", file=sys.stderr)
                sys.exit(1)
        
        if args.json:
            import json
            print(json.dumps({
                "name": info.name,
                "executable": info.executable,
                "version": info.version,
                "available": info.available,
                "install_path": str(info.install_path) if info.install_path else None,
                "global_install_supported": info.global_install_supported,
                "local_install_supported": info.local_install_supported,
            }, indent=2))
        else:
            if info.available:
                print(f"{info.name} {info.version} ({info.executable})")
            else:
                print(f"{info.name}: NOT AVAILABLE")
                sys.exit(1)
    
    else:
        # Detect all managers
        managers = detector.detect_all()
        
        if args.json:
            import json
            result = {}
            for name, info in managers.items():
                result[name] = {
                    "name": info.name,
                    "executable": info.executable,
                    "version": info.version,
                    "available": info.available,
                    "install_path": str(info.install_path) if info.install_path else None,
                    "global_install_supported": info.global_install_supported,
                    "local_install_supported": info.local_install_supported,
                }
            print(json.dumps(result, indent=2))
        else:
            print("Package Manager Detection Results:")
            for name, info in managers.items():
                status = f"{info.version} ({info.executable})" if info.available else "NOT AVAILABLE"
                print(f"  {info.name}: {status}")


if __name__ == "__main__":
    main()
