#!/usr/bin/env python3
"""
Comprehensive tests for BSR Team ORAS Cache system.

This module tests team-optimized caching functionality including shared caches,
dependency bundling, and usage pattern analysis.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the modules we're testing
from bsr_client import BSRClient, BSRDependency, BSRModuleInfo, BSRClientError
from oras_client import OrasClient, OrasClientError
from bsr_team_oras_cache import (
    BSRTeamOrasCache, TeamUsageAnalyzer, SharedTeamCache,
    UsagePattern, CacheStrategy, CachePerformanceMetrics, DependencyBundle
)


class TestBSRDependency(unittest.TestCase):
    """Test BSRDependency data class."""
    
    def test_dependency_creation(self):
        """Test creating a BSR dependency."""
        dep = BSRDependency(
            name="googleapis",
            version="1.0.0",
            digest="sha256:test",
            repository="buf.build/googleapis"
        )
        
        self.assertEqual(dep.name, "googleapis")
        self.assertEqual(dep.version, "v1.0.0")  # Should add 'v' prefix
        self.assertEqual(dep.full_name, "buf.build/googleapis/googleapis")
        self.assertEqual(dep.reference, "buf.build/googleapis/googleapis:v1.0.0")

    def test_dependency_serialization(self):
        """Test dependency serialization."""
        dep = BSRDependency(
            name="test",
            version="v1.0.0",
            digest="sha256:test",
            repository="buf.build/test"
        )
        
        # Test to_dict
        data = dep.to_dict()
        self.assertIn("name", data)
        self.assertIn("version", data)
        
        # Test from_dict
        restored = BSRDependency.from_dict(data)
        self.assertEqual(dep.name, restored.name)
        self.assertEqual(dep.version, restored.version)


class TestTeamUsageAnalyzer(unittest.TestCase):
    """Test team usage pattern analysis."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.analyzer = TeamUsageAnalyzer("test-team", self.cache_dir)

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_track_dependency_access(self):
        """Test tracking dependency access."""
        self.analyzer.track_dependency_access("buf.build/googleapis/googleapis:v1", "alice")
        self.analyzer.track_dependency_access("buf.build/googleapis/googleapis:v1", "bob")
        self.analyzer.track_dependency_access("buf.build/grpc/grpc:v1", "alice")
        
        patterns = self.analyzer.analyze_dependency_patterns()
        
        self.assertEqual(patterns.team, "test-team")
        self.assertEqual(patterns.dependencies["buf.build/googleapis/googleapis:v1"], 2)
        self.assertEqual(patterns.dependencies["buf.build/grpc/grpc:v1"], 1)
        self.assertIn("alice", patterns.team_members)
        self.assertIn("bob", patterns.team_members)

    def test_bundle_opportunities(self):
        """Test identifying bundle opportunities."""
        # Simulate co-occurring dependencies
        current_time = time.time()
        
        # Mock usage data with co-occurring dependencies
        usage_data = {
            "team": "test-team",
            "dependencies": {
                "dep1": 10,
                "dep2": 8,
                "dep3": 12,
                "dep4": 3  # Below threshold
            },
            "time_patterns": {
                "dep1": [current_time - 3600, current_time - 3000, current_time - 2400],
                "dep2": [current_time - 3600, current_time - 3000, current_time - 2400],  # Same times as dep1
                "dep3": [current_time - 7200, current_time - 6600, current_time - 6000],  # Different times
                "dep4": [current_time - 1800]
            },
            "team_members": ["alice", "bob"],
            "common_bundles": [],
            "peak_usage_hours": [],
            "cache_hit_rate": 0.7,
            "bandwidth_usage": 100.0,
            "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        self.analyzer._save_usage_data(usage_data)
        
        opportunities = self.analyzer.identify_bundle_opportunities()
        
        # Should find dep1 and dep2 as bundle candidates (co-occurring)
        self.assertGreater(len(opportunities), 0)
        
        # Find the bundle opportunity for dep1 or dep2
        found_bundle = False
        for opp in opportunities:
            if opp["primary_dependency"] in ["dep1", "dep2"]:
                found_bundle = True
                self.assertGreater(len(opp["related_dependencies"]), 0)
                break
        
        self.assertTrue(found_bundle, "Should find bundle opportunity for co-occurring dependencies")

    def test_cache_recommendations(self):
        """Test cache optimization recommendations."""
        # Set up usage data that will trigger recommendations
        usage_data = {
            "team": "test-team",
            "dependencies": {
                "high_usage_dep": 50,
                "medium_dep1": 15,
                "medium_dep2": 12,
                "medium_dep3": 10,
                "low_usage_dep": 2
            },
            "time_patterns": {},
            "team_members": ["alice", "bob", "charlie"],
            "common_bundles": [],
            "peak_usage_hours": [9, 14, 16],
            "cache_hit_rate": 0.6,  # Low hit rate
            "bandwidth_usage": 500.0,
            "last_updated": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        }
        
        self.analyzer._save_usage_data(usage_data)
        
        recommendations = self.analyzer.recommend_cache_optimizations()
        
        # Should get multiple recommendations
        self.assertGreater(len(recommendations), 0)
        
        # Check for specific recommendation types
        rec_types = [rec["type"] for rec in recommendations]
        self.assertIn("preload_dependencies", rec_types)
        self.assertIn("create_bundle", rec_types)
        self.assertIn("increase_cache_size", rec_types)


class TestSharedTeamCache(unittest.TestCase):
    """Test shared team cache functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.cache_config = {
            "shared_cache_dir": self.temp_dir + "/shared",
            "max_cache_size_mb": 1000
        }
        
        # Mock ORAS client
        self.mock_oras_client = Mock(spec=OrasClient)
        self.shared_cache = SharedTeamCache("test-team", self.cache_config, self.mock_oras_client)

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_setup_shared_cache(self):
        """Test setting up shared cache."""
        team_members = ["alice", "bob", "charlie"]
        result = self.shared_cache.setup_shared_cache(team_members)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["team"], "test-team")
        self.assertEqual(result["members"], team_members)
        
        # Check that directories were created
        self.assertTrue((self.shared_cache.shared_cache_dir / "dependencies").exists())
        self.assertTrue((self.shared_cache.shared_cache_dir / "bundles").exists())
        self.assertTrue((self.shared_cache.shared_cache_dir / "metadata").exists())
        
        # Check that manifest was created
        manifest_path = Path(result["manifest_path"])
        self.assertTrue(manifest_path.exists())
        
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        self.assertEqual(manifest["team"], "test-team")
        self.assertEqual(manifest["members"], team_members)

    def test_sync_cache_updates(self):
        """Test cache synchronization."""
        # Set up some cache structure first
        self.shared_cache.setup_shared_cache(["alice", "bob"])
        
        # Create some mock cached items
        deps_dir = self.shared_cache.shared_cache_dir / "dependencies"
        (deps_dir / "dep1").touch()
        (deps_dir / "dep2").touch()
        
        result = self.shared_cache.sync_cache_updates()
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["team"], "test-team")
        self.assertEqual(result["updates_synced"], 2)


class TestBSRTeamOrasCache(unittest.TestCase):
    """Test the main BSR Team ORAS Cache functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock clients
        self.mock_bsr_client = Mock(spec=BSRClient)
        self.mock_oras_client = Mock(spec=OrasClient)
        self.mock_oras_client.cache_dir = self.temp_dir
        self.mock_oras_client.registry = "test.registry.local"
        
        # Initialize team cache
        self.team_cache = BSRTeamOrasCache(
            team="test-team",
            bsr_client=self.mock_bsr_client,
            oras_client=self.mock_oras_client,
            cache_config={"shared_cache_dir": self.temp_dir + "/shared"}
        )

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_enable_shared_cache(self):
        """Test enabling shared cache for team."""
        team_members = ["alice", "bob", "charlie"]
        result = self.team_cache.enable_shared_cache(team_members)
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["team"], "test-team")
        self.assertEqual(result["members"], team_members)

    def test_create_dependency_bundle(self):
        """Test creating a dependency bundle."""
        # Mock BSR client responses
        mock_dep_metadata = {"size": 1024000}  # 1MB
        self.mock_bsr_client.get_dependency_metadata.return_value = mock_dep_metadata
        
        dependencies = [
            "buf.build/googleapis/googleapis:v1.0.0",
            "buf.build/grpc/grpc:v1.5.0"
        ]
        
        oras_ref = self.team_cache.create_dependency_bundle(
            dependencies=dependencies,
            bundle_name="common-apis",
            description="Common API dependencies for the team"
        )
        
        expected_ref = "test.registry.local/teams/test-team/bundles/common-apis:latest"
        self.assertEqual(oras_ref, expected_ref)
        
        # Verify bundle metadata was saved
        bundle_dir = self.team_cache.shared_cache.shared_cache_dir / "bundles" / "common-apis"
        metadata_file = bundle_dir / "bundle_metadata.json"
        self.assertTrue(metadata_file.exists())
        
        with open(metadata_file) as f:
            metadata = json.load(f)
        
        self.assertEqual(metadata["bundle"]["name"], "common-apis")
        self.assertEqual(len(metadata["dependencies"]), 2)

    def test_optimize_cache_strategy(self):
        """Test cache strategy optimization."""
        # Create mock usage patterns
        usage_patterns = UsagePattern(
            team="test-team",
            dependencies={
                "dep1": 50,  # High usage
                "dep2": 30,
                "dep3": 25,
                "dep4": 20,
                "dep5": 15,
                "dep6": 10,
                "dep7": 8,
                "dep8": 5,
                "dep9": 3,
                "dep10": 1
            },
            time_patterns={},
            team_members=["alice", "bob", "charlie", "david", "eve"],
            common_bundles=[],
            peak_usage_hours=[9, 14, 16],
            cache_hit_rate=0.85,
            bandwidth_usage=200.0,
            last_updated=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        )
        
        strategy = self.team_cache.optimize_cache_strategy(usage_patterns)
        
        self.assertEqual(strategy.team, "test-team")
        self.assertEqual(strategy.cache_type, "balanced")  # Medium usage/deps
        self.assertTrue(strategy.shared_cache_enabled)
        self.assertEqual(strategy.bundle_strategy, "auto")  # Has bundle candidates
        self.assertGreater(len(strategy.preload_dependencies), 0)

    def test_monitor_cache_performance(self):
        """Test cache performance monitoring."""
        # Set up some usage data
        self.team_cache.usage_analyzer.track_dependency_access("dep1", "alice")
        self.team_cache.usage_analyzer.track_dependency_access("dep2", "bob")
        
        metrics = self.team_cache.monitor_cache_performance()
        
        self.assertEqual(metrics.team, "test-team")
        self.assertIsInstance(metrics.cache_hit_rate, float)
        self.assertIsInstance(metrics.build_time_improvement, float)
        self.assertIsInstance(metrics.bandwidth_saved, float)

    def test_get_cache_recommendations(self):
        """Test getting cache recommendations."""
        # Set up usage data that will generate recommendations
        self.team_cache.usage_analyzer.track_dependency_access("high_usage_dep", "alice")
        self.team_cache.usage_analyzer.track_dependency_access("high_usage_dep", "bob")
        self.team_cache.usage_analyzer.track_dependency_access("high_usage_dep", "charlie")
        
        recommendations = self.team_cache.get_cache_recommendations()
        
        self.assertIsInstance(recommendations, list)
        # Should have at least some recommendations
        if recommendations:
            rec = recommendations[0]
            self.assertIn("type", rec)
            self.assertIn("priority", rec)
            self.assertIn("description", rec)

    def test_sync_team_cache(self):
        """Test team cache synchronization."""
        # Set up team first
        self.team_cache.enable_shared_cache(["alice", "bob"])
        
        result = self.team_cache.sync_team_cache()
        
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["team"], "test-team")


class TestUsagePattern(unittest.TestCase):
    """Test UsagePattern data class functionality."""
    
    def test_get_most_used_dependencies(self):
        """Test getting most used dependencies."""
        pattern = UsagePattern(
            team="test",
            dependencies={"dep1": 10, "dep2": 5, "dep3": 15, "dep4": 2},
            time_patterns={},
            team_members=[],
            common_bundles=[],
            peak_usage_hours=[],
            cache_hit_rate=0.8,
            bandwidth_usage=100.0,
            last_updated=""
        )
        
        most_used = pattern.get_most_used_dependencies(2)
        
        self.assertEqual(len(most_used), 2)
        self.assertEqual(most_used[0], ("dep3", 15))
        self.assertEqual(most_used[1], ("dep1", 10))

    def test_get_bundle_candidates(self):
        """Test getting bundle candidates."""
        pattern = UsagePattern(
            team="test",
            dependencies={"dep1": 10, "dep2": 5, "dep3": 15, "dep4": 2},
            time_patterns={},
            team_members=[],
            common_bundles=[],
            peak_usage_hours=[],
            cache_hit_rate=0.8,
            bandwidth_usage=100.0,
            last_updated=""
        )
        
        candidates = pattern.get_bundle_candidates(min_usage=5)
        
        # Should include dep1, dep2, dep3 (usage >= 5) but not dep4
        self.assertIn("dep1", candidates)
        self.assertIn("dep2", candidates)
        self.assertIn("dep3", candidates)
        self.assertNotIn("dep4", candidates)


class TestCacheStrategy(unittest.TestCase):
    """Test CacheStrategy data class functionality."""
    
    def test_cache_strategy_serialization(self):
        """Test cache strategy serialization."""
        strategy = CacheStrategy(
            team="test-team",
            cache_type="aggressive",
            shared_cache_enabled=True,
            bundle_strategy="auto",
            cache_size_limit=2000,
            eviction_policy="lru",
            preload_dependencies=["dep1", "dep2"],
            sync_frequency=30,
            compression_enabled=True
        )
        
        # Test serialization
        data = strategy.to_dict()
        self.assertIn("team", data)
        self.assertIn("cache_type", data)
        
        # Test deserialization
        restored = CacheStrategy.from_dict(data)
        self.assertEqual(strategy.team, restored.team)
        self.assertEqual(strategy.cache_type, restored.cache_type)
        self.assertEqual(strategy.preload_dependencies, restored.preload_dependencies)


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios and workflows."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock clients with more realistic behavior
        self.mock_bsr_client = Mock(spec=BSRClient)
        self.mock_oras_client = Mock(spec=OrasClient)
        self.mock_oras_client.cache_dir = self.temp_dir
        self.mock_oras_client.registry = "oras.birb.homes"
        
        # Mock BSR client responses
        self.mock_bsr_client.get_dependency_metadata.return_value = {
            "size": 1024000,
            "description": "Test dependency",
            "owner": "test-owner"
        }

    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_team_onboarding_workflow(self):
        """Test complete team onboarding workflow."""
        # Initialize team cache
        team_cache = BSRTeamOrasCache(
            team="platform-team",
            bsr_client=self.mock_bsr_client,
            oras_client=self.mock_oras_client,
            cache_config={"shared_cache_dir": self.temp_dir + "/shared"}
        )
        
        # 1. Enable shared cache for team
        team_members = ["alice", "bob", "charlie", "david"]
        setup_result = team_cache.enable_shared_cache(team_members)
        self.assertEqual(setup_result["status"], "success")
        
        # 2. Simulate team usage patterns
        for member in team_members:
            # Common dependencies used by all
            team_cache.usage_analyzer.track_dependency_access("buf.build/googleapis/googleapis:v1", member)
            team_cache.usage_analyzer.track_dependency_access("buf.build/grpc/grpc:v1", member)
        
        # Some members use additional dependencies
        team_cache.usage_analyzer.track_dependency_access("buf.build/envoy/envoy:v1", "alice")
        team_cache.usage_analyzer.track_dependency_access("buf.build/envoy/envoy:v1", "bob")
        
        # 3. Get usage patterns
        patterns = team_cache.usage_analyzer.analyze_dependency_patterns()
        self.assertEqual(len(patterns.team_members), 4)
        self.assertGreater(patterns.dependencies["buf.build/googleapis/googleapis:v1"], 1)
        
        # 4. Optimize cache strategy
        strategy = team_cache.optimize_cache_strategy(patterns)
        self.assertEqual(strategy.team, "platform-team")
        self.assertTrue(strategy.shared_cache_enabled)
        
        # 5. Create bundle for common dependencies
        common_deps = [
            "buf.build/googleapis/googleapis:v1.0.0",
            "buf.build/grpc/grpc:v1.5.0"
        ]
        bundle_ref = team_cache.create_dependency_bundle(
            dependencies=common_deps,
            bundle_name="platform-common",
            description="Common platform dependencies"
        )
        self.assertIn("platform-team/bundles/platform-common", bundle_ref)
        
        # 6. Monitor performance
        metrics = team_cache.monitor_cache_performance()
        self.assertEqual(metrics.team, "platform-team")
        
        # 7. Get recommendations
        recommendations = team_cache.get_cache_recommendations()
        self.assertIsInstance(recommendations, list)

    def test_cache_optimization_workflow(self):
        """Test cache optimization based on usage patterns."""
        team_cache = BSRTeamOrasCache(
            team="backend-team",
            bsr_client=self.mock_bsr_client,
            oras_client=self.mock_oras_client
        )
        
        # Simulate heavy usage patterns
        dependencies = [
            "buf.build/googleapis/googleapis:v1",
            "buf.build/grpc/grpc:v1",
            "buf.build/envoy/envoy:v1",
            "buf.build/istio/istio:v1",
            "buf.build/kubernetes/kubernetes:v1"
        ]
        
        members = ["alice", "bob", "charlie", "david", "eve"]
        
        # Create usage patterns with varying frequencies
        for i, dep in enumerate(dependencies):
            usage_count = 20 - (i * 3)  # Decreasing usage
            for _ in range(usage_count):
                member = members[_ % len(members)]
                team_cache.usage_analyzer.track_dependency_access(dep, member)
        
        # Get optimization recommendations
        recommendations = team_cache.get_cache_recommendations()
        
        # Should recommend preloading high-usage dependencies
        preload_recs = [r for r in recommendations if r["type"] == "preload_dependencies"]
        self.assertGreater(len(preload_recs), 0)
        
        # Should recommend creating bundles
        bundle_recs = [r for r in recommendations if r["type"] in ["create_bundle", "create_specific_bundle"]]
        self.assertGreater(len(bundle_recs), 0)


def run_comprehensive_tests():
    """Run all BSR team cache tests."""
    print("🧪 Running BSR Team ORAS Cache Tests...")
    
    # Create test suite
    test_classes = [
        TestBSRDependency,
        TestTeamUsageAnalyzer,
        TestSharedTeamCache,
        TestBSRTeamOrasCache,
        TestUsagePattern,
        TestCacheStrategy,
        TestIntegrationScenarios
    ]
    
    suite = unittest.TestSuite()
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n📊 Test Results:")
    print(f"  Tests run: {result.testsRun}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.failures:
        print(f"\n❌ Failures:")
        for test, failure in result.failures:
            print(f"  {test}: {failure}")
    
    if result.errors:
        print(f"\n💥 Errors:")
        for test, error in result.errors:
            print(f"  {test}: {error}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("✅ All BSR Team Cache tests passed!")
    else:
        print("❌ Some tests failed!")
    
    return success


if __name__ == "__main__":
    success = run_comprehensive_tests()
    exit(0 if success else 1)
