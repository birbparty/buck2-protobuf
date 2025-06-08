#!/usr/bin/env python3
"""
Comprehensive test for package manager integration.

This script tests the complete package manager → ORAS → HTTP fallback strategy
for protoc plugin installation.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add current directory to Python path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from package_manager_detector import PackageManagerDetector, PackageManagerInfo
    from package_manager_base import PluginSpec, InstallationResult, BasePackageManagerInstaller
    from cargo_plugin_installer import CargoPluginInstaller
    from npm_plugin_installer import NPMPluginInstaller
    from oras_plugins import PluginOrasDistributor
    IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"Import error: {e}")
    IMPORTS_AVAILABLE = False


class TestPackageManagerDetector(unittest.TestCase):
    """Test package manager detection functionality."""
    
    def setUp(self):
        """Set up test environment."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        
        self.detector = PackageManagerDetector(verbose=True)
    
    def test_detect_cargo(self):
        """Test Cargo detection."""
        cargo_info = self.detector.detect_cargo()
        self.assertIsInstance(cargo_info, PackageManagerInfo)
        self.assertEqual(cargo_info.name, "cargo")
        print(f"Cargo detection: {cargo_info.available} (version: {cargo_info.version})")
    
    def test_detect_npm(self):
        """Test NPM detection."""
        npm_info = self.detector.detect_npm()
        self.assertIsInstance(npm_info, PackageManagerInfo)
        self.assertEqual(npm_info.name, "npm")
        print(f"NPM detection: {npm_info.available} (version: {npm_info.version})")
    
    def test_detect_all(self):
        """Test detection of all package managers."""
        managers = self.detector.detect_all()
        self.assertIsInstance(managers, dict)
        
        expected_managers = ["cargo", "npm", "yarn", "pnpm", "pip"]
        for manager in expected_managers:
            self.assertIn(manager, managers)
            self.assertIsInstance(managers[manager], PackageManagerInfo)
        
        available_count = sum(1 for info in managers.values() if info.available)
        print(f"Available package managers: {available_count}/{len(managers)}")
        
        for name, info in managers.items():
            if info.available:
                print(f"  ✓ {name}: {info.version}")
            else:
                print(f"  ✗ {name}: not available")
    
    def test_preferred_node_manager(self):
        """Test preferred Node.js package manager selection."""
        preferred = self.detector.get_preferred_node_manager()
        if preferred:
            self.assertIn(preferred.name, ["pnpm", "yarn", "npm"])
            print(f"Preferred Node.js package manager: {preferred.name}")
        else:
            print("No Node.js package managers available")


class TestCargoIntegration(unittest.TestCase):
    """Test Cargo plugin installer."""
    
    def setUp(self):
        """Set up test environment."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        
        self.temp_dir = tempfile.mkdtemp()
        self.installer = CargoPluginInstaller(self.temp_dir, verbose=True)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_info(self):
        """Test Cargo manager information."""
        info = self.installer.get_manager_info()
        self.assertEqual(info.name, "cargo")
        print(f"Cargo available: {info.available}")
    
    def test_supported_plugins(self):
        """Test supported Rust plugins."""
        plugins = self.installer.get_supported_plugins()
        self.assertIsInstance(plugins, dict)
        
        expected_plugins = ["prost-build", "tonic-build", "protoc-gen-prost"]
        for plugin in expected_plugins:
            if plugin in plugins:
                print(f"  ✓ Rust plugin: {plugin}")
    
    def test_list_available_plugins(self):
        """Test listing available Rust plugins."""
        plugins = self.installer.list_available_plugins()
        self.assertIsInstance(plugins, list)
        
        print("Available Rust plugins:")
        for plugin in plugins:
            print(f"  - {plugin['name']}: {plugin['description']}")


class TestNPMIntegration(unittest.TestCase):
    """Test NPM plugin installer."""
    
    def setUp(self):
        """Set up test environment."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        
        self.temp_dir = tempfile.mkdtemp()
        self.installer = NPMPluginInstaller(self.temp_dir, verbose=True)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_manager_info(self):
        """Test NPM manager information."""
        info = self.installer.get_manager_info()
        print(f"NPM manager: {info.name} (available: {info.available})")
    
    def test_supported_plugins(self):
        """Test supported TypeScript plugins."""
        plugins = self.installer.get_supported_plugins()
        self.assertIsInstance(plugins, dict)
        
        expected_plugins = ["protoc-gen-ts", "ts-proto", "protoc-gen-es"]
        for plugin in expected_plugins:
            if plugin in plugins:
                print(f"  ✓ TypeScript plugin: {plugin}")
    
    def test_list_available_plugins(self):
        """Test listing available TypeScript plugins."""
        plugins = self.installer.list_available_plugins()
        self.assertIsInstance(plugins, list)
        
        print("Available TypeScript plugins:")
        for plugin in plugins:
            print(f"  - {plugin['name']}: {plugin['description']}")


class TestOrasIntegration(unittest.TestCase):
    """Test ORAS plugin distributor with package manager integration."""
    
    def setUp(self):
        """Set up test environment."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        
        self.temp_dir = tempfile.mkdtemp()
        self.distributor = PluginOrasDistributor(
            registry="oras.birb.homes",
            cache_dir=self.temp_dir,
            verbose=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_package_managers_initialized(self):
        """Test that package managers are properly initialized."""
        print(f"Package managers available: {self.distributor.package_managers is not None}")
        if self.distributor.package_managers:
            print("Package manager integration is active")
        else:
            print("Package manager integration is not available")
    
    def test_supported_plugins(self):
        """Test supported plugins list."""
        plugins = self.distributor.get_supported_plugins()
        self.assertIsInstance(plugins, list)
        
        print("Supported plugins via ORAS:")
        for plugin in plugins:
            print(f"  - {plugin}")
    
    def test_supported_bundles(self):
        """Test supported bundles list."""
        bundles = self.distributor.get_supported_bundles()
        self.assertIsInstance(bundles, list)
        
        print("Supported bundles:")
        for bundle in bundles:
            print(f"  - {bundle}")
    
    def test_metrics_structure(self):
        """Test metrics structure includes package manager metrics."""
        metrics = self.distributor.get_performance_metrics()
        self.assertIsInstance(metrics, dict)
        
        expected_metrics = [
            "package_manager_hits", "oras_hits", "http_fallbacks", 
            "cache_hits", "total_requests"
        ]
        
        for metric in expected_metrics:
            self.assertIn(metric, metrics)
        
        print("Performance metrics structure:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")


class TestIntegrationFlow(unittest.TestCase):
    """Test complete integration flow."""
    
    def setUp(self):
        """Set up test environment."""
        if not IMPORTS_AVAILABLE:
            self.skipTest("Required imports not available")
        
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_plugin_spec_creation(self):
        """Test plugin specification creation."""
        spec = PluginSpec(
            name="protoc-gen-go",
            version="1.35.2",
            binary_name="protoc-gen-go"
        )
        
        self.assertEqual(spec.name, "protoc-gen-go")
        self.assertEqual(spec.version, "1.35.2")
        self.assertEqual(spec.binary_name, "protoc-gen-go")
        self.assertTrue(spec.global_install)
        self.assertFalse(spec.optional)
        
        print("Plugin specification creation: ✓")
    
    def test_installation_result_structure(self):
        """Test installation result structure."""
        result = InstallationResult(
            success=True,
            plugin_name="test-plugin",
            binary_path=Path("/tmp/test"),
            method="package_manager"
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.plugin_name, "test-plugin")
        self.assertEqual(result.method, "package_manager")
        
        print("Installation result structure: ✓")


def run_integration_tests():
    """Run integration tests with detailed output."""
    print("="*60)
    print("Package Manager Integration Test Suite")
    print("="*60)
    
    if not IMPORTS_AVAILABLE:
        print("❌ Required imports not available. Please check your Python environment.")
        return False
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestPackageManagerDetector,
        TestCargoIntegration,
        TestNPMIntegration,
        TestOrasIntegration,
        TestIntegrationFlow,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return len(result.failures) == 0 and len(result.errors) == 0


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Package Manager Integration Tests")
    parser.add_argument("--test", choices=["detector", "cargo", "npm", "oras", "integration", "all"], 
                       default="all", help="Specific test to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    if args.verbose:
        print("Verbose mode enabled")
    
    if args.test == "all":
        success = run_integration_tests()
        sys.exit(0 if success else 1)
    else:
        # Run specific test
        if args.test == "detector":
            suite = unittest.TestLoader().loadTestsFromTestCase(TestPackageManagerDetector)
        elif args.test == "cargo":
            suite = unittest.TestLoader().loadTestsFromTestCase(TestCargoIntegration)
        elif args.test == "npm":
            suite = unittest.TestLoader().loadTestsFromTestCase(TestNPMIntegration)
        elif args.test == "oras":
            suite = unittest.TestLoader().loadTestsFromTestCase(TestOrasIntegration)
        elif args.test == "integration":
            suite = unittest.TestLoader().loadTestsFromTestCase(TestIntegrationFlow)
        
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
