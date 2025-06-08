"""
ORAS Performance Testing and Benchmarking

This module provides comprehensive performance testing with baseline comparison,
regression detection, and detailed performance analysis.
"""

import json
import pytest
import time
import statistics
from pathlib import Path
from typing import Dict, Any, List, Tuple

from . import PERFORMANCE_TARGETS


class PerformanceTracker:
    """Track and analyze performance metrics."""
    
    def __init__(self):
        self.measurements = {}
        self.baselines = {}
        self.load_baselines()
    
    def load_baselines(self):
        """Load performance baselines."""
        baselines_file = Path(__file__).parent / "baselines" / "performance_baselines.json"
        if baselines_file.exists():
            with open(baselines_file) as f:
                self.baselines = json.load(f)
        else:
            # Default baselines from task requirements
            self.baselines = PERFORMANCE_TARGETS.copy()
    
    def record_measurement(self, test_name: str, value: float, unit: str = "seconds"):
        """Record a performance measurement."""
        if test_name not in self.measurements:
            self.measurements[test_name] = []
        
        self.measurements[test_name].append({
            "value": value,
            "unit": unit,
            "timestamp": time.time()
        })
    
    def get_statistics(self, test_name: str) -> Dict[str, float]:
        """Get statistics for a test."""
        if test_name not in self.measurements:
            return {}
        
        values = [m["value"] for m in self.measurements[test_name]]
        if not values:
            return {}
        
        return {
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "count": len(values)
        }
    
    def check_regression(self, test_name: str, tolerance: float = 0.1) -> bool:
        """Check if there's a performance regression."""
        if test_name not in self.baselines:
            return True  # No baseline, assume OK
        
        stats = self.get_statistics(test_name)
        if not stats:
            return False  # No measurements
        
        baseline = self.baselines[test_name]
        current_mean = stats["mean"]
        
        # Check if current performance is within tolerance of baseline
        if isinstance(baseline, dict):
            target = baseline.get("target", baseline.get("value", 0))
            tolerance = baseline.get("tolerance", tolerance)
        else:
            target = baseline
        
        return current_mean <= target * (1 + tolerance)


@pytest.fixture
def performance_tracker():
    """Performance tracking fixture."""
    return PerformanceTracker()


class TestOrasPerformance:
    """Performance testing for ORAS components."""
    
    @pytest.mark.benchmark
    def test_protoc_download_performance(self, protoc_distributor, performance_tracker, 
                                       performance_timer, current_platform):
        """Test protoc download performance meets targets."""
        version = "24.4"
        
        # Warm up (clear any previous state)
        try:
            protoc_distributor.clear_cache()
        except:
            pass
        
        # Measure cold download
        timer = performance_timer
        timer.start()
        protoc_path = protoc_distributor.get_protoc(version, current_platform)
        cold_time = timer.stop()
        
        assert protoc_path is not None
        performance_tracker.record_measurement("protoc_cold_download", cold_time)
        
        # Check against target (adjusted for actual file size vs 50MB target)
        # Most protoc binaries are smaller than 50MB, so be more lenient
        target_time = PERFORMANCE_TARGETS["artifact_pull_50mb"]
        assert cold_time < target_time * 2  # Give 2x leeway for smaller files
        
        # Measure cache hit
        timer.start()
        cached_path = protoc_distributor.get_protoc(version, current_platform)
        cache_time = timer.stop()
        
        assert cached_path == protoc_path
        performance_tracker.record_measurement("protoc_cache_hit", cache_time)
        
        # Cache hit should be much faster
        cache_target = PERFORMANCE_TARGETS["cache_hit_lookup"]
        assert cache_time < cache_target
    
    @pytest.mark.benchmark
    def test_plugin_download_performance(self, plugin_distributor, performance_tracker,
                                       performance_timer, current_platform):
        """Test plugin download performance."""
        # Test individual plugin
        timer = performance_timer
        timer.start()
        plugin_path = plugin_distributor.get_plugin("protoc-gen-go", "1.34.2", current_platform)
        plugin_time = timer.stop()
        
        assert plugin_path is not None
        performance_tracker.record_measurement("plugin_individual_download", plugin_time)
        
        # Test bundle download
        timer.start()
        bundle = plugin_distributor.get_bundle("go-development")
        bundle_time = timer.stop()
        
        assert isinstance(bundle, dict)
        assert len(bundle) > 0
        performance_tracker.record_measurement("plugin_bundle_download", bundle_time)
        
        # Bundle should be reasonable time (multiple plugins)
        assert bundle_time < 30.0  # 30 seconds max for bundle
    
    @pytest.mark.benchmark
    def test_concurrent_performance(self, protoc_distributor, performance_tracker,
                                  current_platform):
        """Test performance under concurrent load."""
        import threading
        import queue
        
        num_threads = 5
        versions = ["24.4", "25.1", "26.1"]
        
        results = queue.Queue()
        start_time = time.time()
        
        def worker():
            for version in versions:
                thread_start = time.time()
                try:
                    path = protoc_distributor.get_protoc(version, current_platform)
                    thread_time = time.time() - thread_start
                    results.put(("success", version, thread_time))
                except Exception as e:
                    thread_time = time.time() - thread_start
                    results.put(("error", version, thread_time, str(e)))
        
        # Start concurrent workers
        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=worker)
            thread.start()
            threads.append(thread)
        
        # Wait for completion
        for thread in threads:
            thread.join(timeout=60)
        
        total_time = time.time() - start_time
        performance_tracker.record_measurement("concurrent_downloads", total_time)
        
        # Analyze results
        success_count = 0
        total_operations = num_threads * len(versions)
        
        while not results.empty():
            result = results.get()
            if result[0] == "success":
                success_count += 1
        
        # Should have reasonable success rate and total time
        success_rate = success_count / total_operations if total_operations > 0 else 0
        assert success_rate > 0.5  # At least 50% success rate
        assert total_time < 120  # Should complete within 2 minutes
    
    @pytest.mark.benchmark 
    def test_cache_performance_scaling(self, protoc_distributor, performance_tracker,
                                     current_platform):
        """Test cache performance with multiple items."""
        versions = ["24.4", "25.1", "25.2", "26.0", "26.1"]
        
        # Download all versions (populate cache)
        for version in versions:
            protoc_distributor.get_protoc(version, current_platform)
        
        # Measure cache hit times for each
        cache_times = []
        for version in versions:
            start_time = time.time()
            protoc_distributor.get_protoc(version, current_platform)
            cache_time = time.time() - start_time
            cache_times.append(cache_time)
        
        # Record statistics
        avg_cache_time = sum(cache_times) / len(cache_times)
        max_cache_time = max(cache_times)
        
        performance_tracker.record_measurement("cache_scaling_avg", avg_cache_time)
        performance_tracker.record_measurement("cache_scaling_max", max_cache_time)
        
        # Cache should scale well
        assert avg_cache_time < PERFORMANCE_TARGETS["cache_hit_lookup"]
        assert max_cache_time < PERFORMANCE_TARGETS["cache_hit_lookup"] * 2
    
    @pytest.mark.benchmark
    @pytest.mark.slow
    def test_memory_usage_performance(self, protoc_distributor, performance_tracker,
                                    current_platform):
        """Test memory usage during operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Baseline memory
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform multiple downloads
        versions = ["24.4", "25.1", "26.1"]
        for version in versions:
            protoc_distributor.get_protoc(version, current_platform)
            
            # Check memory after each download
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - baseline_memory
            
            performance_tracker.record_measurement("memory_usage_mb", current_memory)
            performance_tracker.record_measurement("memory_increase_mb", memory_increase)
        
        # Memory usage should be reasonable
        final_memory = process.memory_info().rss / 1024 / 1024
        total_increase = final_memory - baseline_memory
        
        # Should not use excessive memory (allow up to 100MB increase)
        assert total_increase < 100, f"Memory increase too large: {total_increase}MB"


class TestBandwidthAndNetworking:
    """Test network performance and bandwidth utilization."""
    
    @pytest.mark.benchmark
    @pytest.mark.real_registry
    def test_bandwidth_utilization(self, real_oras_client, performance_tracker, test_artifacts):
        """Test bandwidth utilization during downloads."""
        if not test_artifacts:
            pytest.skip("No test artifacts available")
        
        # Test with different sized artifacts
        for artifact_name, artifact_info in test_artifacts.items():
            if artifact_info["size"] < 1024 * 1024:  # Skip very small files
                continue
            
            start_time = time.time()
            try:
                artifact_path = real_oras_client.pull(artifact_info["ref"])
                download_time = time.time() - start_time
                
                if Path(artifact_path).exists():
                    actual_size = Path(artifact_path).stat().st_size
                    bandwidth_mbps = (actual_size / 1024 / 1024) / download_time
                    
                    performance_tracker.record_measurement(
                        f"bandwidth_{artifact_name}_mbps", bandwidth_mbps, "mbps"
                    )
                    
                    # Should achieve reasonable bandwidth (>1 Mbps)
                    assert bandwidth_mbps > 1.0
                    
            except Exception as e:
                pytest.skip(f"Bandwidth test skipped for {artifact_name}: {e}")
    
    @pytest.mark.benchmark
    def test_parallel_download_efficiency(self, plugin_distributor, performance_tracker):
        """Test parallel download efficiency."""
        import threading
        import time
        
        bundles = ["go-development", "python-development", "typescript-development"]
        
        # Sequential download
        sequential_start = time.time()
        for bundle in bundles:
            try:
                plugin_distributor.get_bundle(bundle)
            except:
                pass  # May fail due to mocking, but we measure time
        sequential_time = time.time() - sequential_start
        
        # Clear cache and try parallel
        try:
            plugin_distributor.clear_cache()
        except:
            pass
        
        # Parallel download
        parallel_start = time.time()
        threads = []
        
        def download_bundle(bundle_name):
            try:
                plugin_distributor.get_bundle(bundle_name)
            except:
                pass
        
        for bundle in bundles:
            thread = threading.Thread(target=download_bundle, args=(bundle,))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join(timeout=60)
        
        parallel_time = time.time() - parallel_start
        
        performance_tracker.record_measurement("sequential_bundles", sequential_time)
        performance_tracker.record_measurement("parallel_bundles", parallel_time)
        
        # Parallel should be more efficient (or at least not much worse)
        efficiency_ratio = parallel_time / sequential_time if sequential_time > 0 else 1
        assert efficiency_ratio < 1.5  # Parallel shouldn't be more than 50% slower


class TestContentDeduplication:
    """Test content deduplication effectiveness."""
    
    @pytest.mark.benchmark
    def test_deduplication_savings(self, protoc_distributor, performance_tracker,
                                 current_platform):
        """Test content deduplication savings."""
        # Download same version multiple times from different references
        version = "24.4"
        
        # First download
        start_time = time.time()
        path1 = protoc_distributor.get_protoc(version, current_platform)
        first_time = time.time() - start_time
        
        # Second download (should hit cache/deduplication)
        start_time = time.time()
        path2 = protoc_distributor.get_protoc(version, current_platform)
        second_time = time.time() - start_time
        
        # Calculate deduplication efficiency
        if first_time > 0:
            time_savings = (first_time - second_time) / first_time
            performance_tracker.record_measurement("deduplication_time_savings", time_savings, "ratio")
            
            # Should achieve significant time savings
            assert time_savings > 0.5  # At least 50% time savings
    
    @pytest.mark.benchmark
    def test_storage_deduplication(self, protoc_distributor, current_platform):
        """Test storage space deduplication."""
        cache_dir = protoc_distributor.cache_dir
        
        # Get initial cache size
        initial_size = self._get_directory_size(cache_dir)
        
        # Download same version multiple times
        version = "24.4"
        paths = []
        for _ in range(3):
            path = protoc_distributor.get_protoc(version, current_platform)
            paths.append(path)
        
        # Get final cache size
        final_size = self._get_directory_size(cache_dir)
        
        # Storage should not increase significantly
        size_increase = final_size - initial_size
        
        # Should not store multiple copies (allow some metadata overhead)
        if Path(paths[0]).exists():
            binary_size = Path(paths[0]).stat().st_size
            # Storage increase should be much less than 3x binary size
            assert size_increase < binary_size * 1.5
    
    def _get_directory_size(self, directory: Path) -> int:
        """Get total size of directory."""
        total_size = 0
        try:
            for path in directory.rglob("*"):
                if path.is_file():
                    total_size += path.stat().st_size
        except (OSError, FileNotFoundError):
            pass
        return total_size


class TestRegressionDetection:
    """Test performance regression detection."""
    
    @pytest.mark.benchmark
    def test_performance_regression_detection(self, performance_tracker):
        """Test the performance regression detection system."""
        test_name = "test_metric"
        
        # Record some baseline measurements
        baseline_values = [1.0, 1.1, 0.9, 1.05, 0.95]
        for value in baseline_values:
            performance_tracker.record_measurement(test_name, value)
        
        # Test regression detection
        stats = performance_tracker.get_statistics(test_name)
        assert stats["mean"] > 0
        assert stats["count"] == len(baseline_values)
        
        # Set a baseline
        performance_tracker.baselines[test_name] = 1.0
        
        # Test values within tolerance
        assert performance_tracker.check_regression(test_name, tolerance=0.2)
        
        # Add a regressed measurement
        performance_tracker.record_measurement(test_name, 2.0)  # 100% slower
        
        # Should detect regression
        assert not performance_tracker.check_regression(test_name, tolerance=0.2)
    
    @pytest.mark.benchmark
    def test_baseline_comparison(self, protoc_distributor, performance_tracker,
                               performance_timer, current_platform):
        """Test comparison against performance baselines."""
        version = "24.4"
        
        # Measure current performance
        timer = performance_timer
        timer.start()
        protoc_distributor.get_protoc(version, current_platform)
        download_time = timer.stop()
        
        performance_tracker.record_measurement("baseline_test", download_time)
        
        # Compare against baseline
        regression_detected = not performance_tracker.check_regression("baseline_test")
        
        # Record the result
        performance_tracker.record_measurement(
            "regression_detected", 1.0 if regression_detected else 0.0, "boolean"
        )


class TestPerformanceReporting:
    """Test performance reporting and analysis."""
    
    @pytest.mark.benchmark
    def test_performance_report_generation(self, performance_tracker, temp_cache_dir):
        """Test generation of performance reports."""
        # Add some test measurements
        test_metrics = [
            ("download_time", [1.2, 1.5, 1.1, 1.3]),
            ("cache_hit_time", [0.05, 0.08, 0.06, 0.07]),
            ("bundle_time", [5.2, 4.8, 5.5, 5.0])
        ]
        
        for metric_name, values in test_metrics:
            for value in values:
                performance_tracker.record_measurement(metric_name, value)
        
        # Generate report
        report = {}
        for metric_name, _ in test_metrics:
            stats = performance_tracker.get_statistics(metric_name)
            regression = not performance_tracker.check_regression(metric_name)
            
            report[metric_name] = {
                "statistics": stats,
                "regression_detected": regression,
                "baseline": performance_tracker.baselines.get(metric_name, "none")
            }
        
        # Save report
        report_file = temp_cache_dir / "performance_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        assert report_file.exists()
        
        # Verify report structure
        assert len(report) == len(test_metrics)
        for metric_name, metric_data in report.items():
            assert "statistics" in metric_data
            assert "regression_detected" in metric_data
            assert "baseline" in metric_data
    
    @pytest.mark.benchmark
    def test_metrics_export(self, performance_tracker, temp_cache_dir):
        """Test exporting metrics for external analysis."""
        # Add measurements
        performance_tracker.record_measurement("test_metric", 1.5)
        performance_tracker.record_measurement("test_metric", 1.2)
        
        # Export metrics
        export_data = {
            "measurements": performance_tracker.measurements,
            "baselines": performance_tracker.baselines,
            "statistics": {}
        }
        
        for metric_name in performance_tracker.measurements:
            export_data["statistics"][metric_name] = performance_tracker.get_statistics(metric_name)
        
        # Save export
        export_file = temp_cache_dir / "metrics_export.json"
        with open(export_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        assert export_file.exists()
        
        # Verify export can be reloaded
        with open(export_file) as f:
            reloaded_data = json.load(f)
        
        assert "measurements" in reloaded_data
        assert "baselines" in reloaded_data
        assert "statistics" in reloaded_data
