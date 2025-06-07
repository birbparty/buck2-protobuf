#!/usr/bin/env python3
"""
Comprehensive performance benchmark suite for protobuf Buck2 integration.

This module provides systematic performance benchmarking to validate
all performance targets and detect regressions.
"""

import os
import sys
import time
import json
import statistics
import subprocess
import tempfile
import threading
import psutil
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from test.test_utils import ProtoTestCase, create_test_proto_file, run_command


@dataclass
class BenchmarkResult:
    """Represents a single benchmark result."""
    name: str
    duration_ms: float
    memory_mb: float
    cpu_percent: float
    success: bool
    target_met: bool
    target_ms: Optional[float] = None
    iterations: int = 1
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PerformanceTargets:
    """Performance targets for different operations."""
    small_proto_ms: float = 2000        # Small proto compilation < 2s
    medium_proto_ms: float = 10000      # Medium proto compilation < 10s
    large_proto_ms: float = 30000       # Large proto compilation < 30s
    incremental_ms: float = 500         # Incremental build < 500ms
    cache_hit_ms: float = 100           # Cache hit < 100ms
    multi_language_ms: float = 5000     # Multi-language bundle < 5s
    memory_limit_mb: float = 1024       # Memory usage < 1GB
    
    # Stress testing targets
    concurrent_builds: int = 10         # Handle 10 concurrent builds
    large_dependency_chain: int = 100   # Handle 100-deep dependency chain
    file_count_limit: int = 1000        # Handle 1000 proto files


class PerformanceBenchmarks:
    """Comprehensive performance benchmark suite."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.targets = PerformanceTargets()
        self.results: List[BenchmarkResult] = []
        self.temp_dir = Path(tempfile.mkdtemp(prefix="perf_bench_"))
        
    def setup_benchmark_environment(self):
        """Set up isolated benchmark environment."""
        print("🚀 Setting up performance benchmark environment...")
        
        # Create benchmark workspace
        workspace = self.temp_dir / "workspace"
        workspace.mkdir(parents=True, exist_ok=True)
        
        # Copy necessary files
        for item in ["rules", "tools", "platforms", ".buckconfig"]:
            src = self.project_root / item
            dst = workspace / item
            if src.is_dir():
                import shutil
                shutil.copytree(src, dst)
            else:
                import shutil
                shutil.copy2(src, dst)
        
        # Create benchmark-specific proto files
        self._create_benchmark_protos(workspace)
        
        os.chdir(workspace)
        print("✓ Benchmark environment ready")
    
    def cleanup_benchmark_environment(self):
        """Clean up benchmark environment."""
        print("🧹 Cleaning up benchmark environment...")
        os.chdir(self.project_root)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks."""
        print("⚡ Starting comprehensive performance benchmarks...")
        
        # Setup environment
        self.setup_benchmark_environment()
        
        try:
            # Core performance benchmarks
            self._benchmark_proto_compilation()
            self._benchmark_incremental_builds()
            self._benchmark_cache_performance()
            self._benchmark_multi_language_generation()
            self._benchmark_dependency_resolution()
            
            # Stress testing benchmarks
            self._benchmark_concurrent_builds()
            self._benchmark_large_dependency_chains()
            self._benchmark_file_count_scalability()
            self._benchmark_memory_usage()
            
            # Performance regression detection
            self._benchmark_performance_regression()
            
            # Generate comprehensive report
            return self._generate_performance_report()
            
        finally:
            self.cleanup_benchmark_environment()
    
    def _create_benchmark_protos(self, workspace: Path):
        """Create proto files for benchmarking."""
        bench_dir = workspace / "bench"
        bench_dir.mkdir(parents=True, exist_ok=True)
        
        # Small proto (minimal complexity)
        self._create_small_proto(bench_dir)
        
        # Medium proto (moderate complexity)
        self._create_medium_proto(bench_dir)
        
        # Large proto (high complexity)
        self._create_large_proto(bench_dir)
        
        # Dependency chain protos
        self._create_dependency_chain_protos(bench_dir)
        
        # Multi-language bundle protos
        self._create_multi_language_bundle_protos(bench_dir)
        
        # Create BUCK file for benchmarks
        self._create_benchmark_buck_file(bench_dir)
    
    def _create_small_proto(self, bench_dir: Path):
        """Create small proto for basic performance testing."""
        proto_content = """
syntax = "proto3";

package bench.small;

message SmallMessage {
  string name = 1;
  int32 id = 2;
  bool active = 3;
}
"""
        (bench_dir / "small.proto").write_text(proto_content.strip())
    
    def _create_medium_proto(self, bench_dir: Path):
        """Create medium complexity proto."""
        fields = []
        for i in range(50):
            field_type = ["string", "int32", "int64", "bool", "double"][i % 5]
            fields.append(f"  {field_type} field_{i} = {i + 1};")
        
        proto_content = f"""
syntax = "proto3";

package bench.medium;

import "google/protobuf/timestamp.proto";

message MediumMessage {{
{chr(10).join(fields)}
  google.protobuf.Timestamp created_at = 51;
  repeated string tags = 52;
  map<string, string> metadata = 53;
}}

enum MediumEnum {{
  UNKNOWN = 0;
  FIRST = 1;
  SECOND = 2;
  THIRD = 3;
}}

service MediumService {{
  rpc GetMedium(MediumMessage) returns (MediumMessage);
  rpc ListMedium(MediumMessage) returns (stream MediumMessage);
}}
"""
        (bench_dir / "medium.proto").write_text(proto_content.strip())
    
    def _create_large_proto(self, bench_dir: Path):
        """Create large, complex proto for stress testing."""
        # Generate many fields
        fields = []
        for i in range(500):
            field_type = ["string", "int32", "int64", "bool", "double", "bytes"][i % 6]
            fields.append(f"  {field_type} field_{i} = {i + 1};")
        
        # Generate many enum values
        enum_values = ["  UNKNOWN = 0;"]
        for i in range(100):
            enum_values.append(f"  VALUE_{i} = {i + 1};")
        
        # Generate many service methods
        methods = []
        for i in range(50):
            methods.append(f"  rpc Method_{i}(LargeMessage) returns (LargeMessage);")
        
        proto_content = f"""
syntax = "proto3";

package bench.large;

import "google/protobuf/timestamp.proto";
import "google/protobuf/duration.proto";
import "google/protobuf/any.proto";

message LargeMessage {{
{chr(10).join(fields)}
  
  // Nested messages
  message NestedMessage {{
    string value = 1;
    repeated string items = 2;
    map<string, int32> counts = 3;
  }}
  
  repeated NestedMessage nested_messages = 501;
  map<string, NestedMessage> nested_map = 502;
  
  // Well-known types
  google.protobuf.Timestamp timestamp = 503;
  google.protobuf.Duration duration = 504;
  google.protobuf.Any any_field = 505;
  
  // Oneof
  oneof large_oneof {{
    string string_choice = 506;
    int64 int_choice = 507;
    NestedMessage message_choice = 508;
  }}
}}

enum LargeEnum {{
{chr(10).join(enum_values)}
}}

service LargeService {{
{chr(10).join(methods)}
}}
"""
        (bench_dir / "large.proto").write_text(proto_content.strip())
    
    def _create_dependency_chain_protos(self, bench_dir: Path):
        """Create chain of proto dependencies for dependency resolution testing."""
        chain_dir = bench_dir / "chain"
        chain_dir.mkdir(exist_ok=True)
        
        # Create base proto
        base_content = """
syntax = "proto3";

package bench.chain;

message BaseMessage {
  string id = 1;
  string name = 2;
}
"""
        (chain_dir / "base.proto").write_text(base_content.strip())
        
        # Create chain of dependencies
        for i in range(20):
            deps = ["bench/chain/base.proto"] if i == 0 else [f"bench/chain/level_{i-1}.proto"]
            import_lines = "\n".join([f'import "{dep}";' for dep in deps])
            
            prev_msg = "BaseMessage" if i == 0 else f"Level{i-1}Message"
            
            content = f"""
syntax = "proto3";

package bench.chain;

{import_lines}

message Level{i}Message {{
  string level_{i}_field = 1;
  bench.chain.{prev_msg} base = 2;
}}
"""
            (chain_dir / f"level_{i}.proto").write_text(content.strip())
    
    def _create_multi_language_bundle_protos(self, bench_dir: Path):
        """Create protos for multi-language bundle testing."""
        bundle_dir = bench_dir / "bundle"
        bundle_dir.mkdir(exist_ok=True)
        
        # Common types
        common_content = """
syntax = "proto3";

package bench.bundle;

message CommonMessage {
  string id = 1;
  string name = 2;
  repeated string tags = 3;
  map<string, string> metadata = 4;
}

enum CommonEnum {
  UNKNOWN = 0;
  ACTIVE = 1;
  INACTIVE = 2;
}
"""
        (bundle_dir / "common.proto").write_text(common_content.strip())
        
        # Service definition
        service_content = """
syntax = "proto3";

package bench.bundle;

import "bench/bundle/common.proto";

service BundleService {
  rpc GetCommon(GetCommonRequest) returns (CommonMessage);
  rpc ListCommon(ListCommonRequest) returns (stream CommonMessage);
}

message GetCommonRequest {
  string id = 1;
}

message ListCommonRequest {
  int32 limit = 1;
  string cursor = 2;
}
"""
        (bundle_dir / "service.proto").write_text(service_content.strip())
    
    def _create_benchmark_buck_file(self, bench_dir: Path):
        """Create BUCK file for benchmark targets."""
        buck_content = """
load("//rules:proto.bzl", "proto_library")
load("//rules:go.bzl", "go_proto_library")
load("//rules:python.bzl", "python_proto_library")
load("//rules:typescript.bzl", "typescript_proto_library")

# Small proto
proto_library(
    name = "small_proto",
    srcs = ["small.proto"],
    visibility = ["PUBLIC"],
)

# Medium proto
proto_library(
    name = "medium_proto",
    srcs = ["medium.proto"],
    visibility = ["PUBLIC"],
)

# Large proto
proto_library(
    name = "large_proto",
    srcs = ["large.proto"],
    visibility = ["PUBLIC"],
)

# Dependency chain
proto_library(
    name = "chain_base_proto",
    srcs = ["chain/base.proto"],
    visibility = ["PUBLIC"],
)

# Bundle protos
proto_library(
    name = "bundle_common_proto",
    srcs = ["bundle/common.proto"],
    visibility = ["PUBLIC"],
)

proto_library(
    name = "bundle_service_proto",
    srcs = ["bundle/service.proto"],
    deps = [":bundle_common_proto"],
    visibility = ["PUBLIC"],
)

# Multi-language targets for bundle testing
go_proto_library(
    name = "bundle_common_go",
    proto = ":bundle_common_proto",
    visibility = ["PUBLIC"],
)

python_proto_library(
    name = "bundle_common_python",
    proto = ":bundle_common_proto",
    visibility = ["PUBLIC"],
)

typescript_proto_library(
    name = "bundle_common_typescript",
    proto = ":bundle_common_proto",
    visibility = ["PUBLIC"],
)
"""
        
        # Add dependency chain targets
        for i in range(20):
            deps = [":chain_base_proto"] if i == 0 else [f":chain_level_{i-1}_proto"]
            deps_str = ", ".join([f'"{dep}"' for dep in deps])
            
            buck_content += f"""
proto_library(
    name = "chain_level_{i}_proto",
    srcs = ["chain/level_{i}.proto"],
    deps = [{deps_str}],
    visibility = ["PUBLIC"],
)
"""
        
        (bench_dir / "BUCK").write_text(buck_content.strip())
    
    def _benchmark_proto_compilation(self):
        """Benchmark basic proto compilation performance."""
        print("📊 Benchmarking proto compilation performance...")
        
        # Small proto benchmark
        result = self._run_benchmark(
            "Small Proto Compilation",
            lambda: self._build_target("//bench:small_proto"),
            target_ms=self.targets.small_proto_ms,
            iterations=5
        )
        self.results.append(result)
        
        # Medium proto benchmark
        result = self._run_benchmark(
            "Medium Proto Compilation",
            lambda: self._build_target("//bench:medium_proto"),
            target_ms=self.targets.medium_proto_ms,
            iterations=3
        )
        self.results.append(result)
        
        # Large proto benchmark
        result = self._run_benchmark(
            "Large Proto Compilation",
            lambda: self._build_target("//bench:large_proto"),
            target_ms=self.targets.large_proto_ms,
            iterations=1
        )
        self.results.append(result)
    
    def _benchmark_incremental_builds(self):
        """Benchmark incremental build performance."""
        print("📊 Benchmarking incremental build performance...")
        
        # First build (cold)
        self._build_target("//bench:small_proto")
        
        # Incremental build (should be fast)
        result = self._run_benchmark(
            "Incremental Build",
            lambda: self._build_target("//bench:small_proto"),
            target_ms=self.targets.incremental_ms,
            iterations=5
        )
        self.results.append(result)
    
    def _benchmark_cache_performance(self):
        """Benchmark cache hit performance."""
        print("📊 Benchmarking cache performance...")
        
        # Populate cache
        self._build_target("//bench:small_proto")
        
        # Cache hit benchmark
        result = self._run_benchmark(
            "Cache Hit Performance",
            lambda: self._build_target("//bench:small_proto"),
            target_ms=self.targets.cache_hit_ms,
            iterations=10
        )
        self.results.append(result)
    
    def _benchmark_multi_language_generation(self):
        """Benchmark multi-language code generation."""
        print("📊 Benchmarking multi-language generation...")
        
        targets = [
            "//bench:bundle_common_go",
            "//bench:bundle_common_python", 
            "//bench:bundle_common_typescript"
        ]
        
        result = self._run_benchmark(
            "Multi-Language Generation",
            lambda: self._build_targets(targets),
            target_ms=self.targets.multi_language_ms,
            iterations=3
        )
        self.results.append(result)
    
    def _benchmark_dependency_resolution(self):
        """Benchmark dependency resolution performance."""
        print("📊 Benchmarking dependency resolution...")
        
        # Build final target in dependency chain
        result = self._run_benchmark(
            "Dependency Resolution",
            lambda: self._build_target("//bench:chain_level_19_proto"),
            target_ms=self.targets.large_proto_ms,  # Use large proto target
            iterations=2
        )
        self.results.append(result)
    
    def _benchmark_concurrent_builds(self):
        """Benchmark concurrent build performance."""
        print("📊 Benchmarking concurrent builds...")
        
        def concurrent_builds():
            targets = [
                "//bench:small_proto",
                "//bench:medium_proto", 
                "//bench:bundle_common_proto",
                "//bench:chain_level_5_proto",
                "//bench:chain_level_10_proto"
            ]
            
            with ThreadPoolExecutor(max_workers=self.targets.concurrent_builds) as executor:
                futures = [
                    executor.submit(self._build_target, target)
                    for target in targets * 2  # Build each target twice
                ]
                
                # Wait for all to complete
                for future in as_completed(futures):
                    future.result()
        
        result = self._run_benchmark(
            "Concurrent Builds",
            concurrent_builds,
            target_ms=self.targets.large_proto_ms * 2,  # Allow more time for concurrent
            iterations=1
        )
        self.results.append(result)
    
    def _benchmark_large_dependency_chains(self):
        """Benchmark handling of large dependency chains."""
        print("📊 Benchmarking large dependency chains...")
        
        # Build the deepest dependency target
        result = self._run_benchmark(
            "Large Dependency Chain",
            lambda: self._build_target("//bench:chain_level_19_proto"),
            target_ms=self.targets.large_proto_ms,
            iterations=1
        )
        self.results.append(result)
    
    def _benchmark_file_count_scalability(self):
        """Benchmark scalability with many proto files."""
        print("📊 Benchmarking file count scalability...")
        
        # Build all chain targets at once
        chain_targets = [f"//bench:chain_level_{i}_proto" for i in range(20)]
        
        result = self._run_benchmark(
            "File Count Scalability",
            lambda: self._build_targets(chain_targets),
            target_ms=self.targets.large_proto_ms * 2,
            iterations=1
        )
        self.results.append(result)
    
    def _benchmark_memory_usage(self):
        """Benchmark memory usage during builds."""
        print("📊 Benchmarking memory usage...")
        
        # Monitor memory during large build
        memory_usage = []
        
        def monitor_memory():
            while self._memory_monitor_active:
                memory_usage.append(psutil.virtual_memory().used / 1024 / 1024)  # MB
                time.sleep(0.1)
        
        self._memory_monitor_active = True
        monitor_thread = threading.Thread(target=monitor_memory)
        monitor_thread.start()
        
        try:
            # Run memory-intensive build
            start_time = time.time()
            self._build_target("//bench:large_proto")
            duration_ms = (time.time() - start_time) * 1000
            
            # Stop monitoring
            self._memory_monitor_active = False
            monitor_thread.join()
            
            # Calculate memory metrics
            max_memory = max(memory_usage) if memory_usage else 0
            avg_memory = statistics.mean(memory_usage) if memory_usage else 0
            
            result = BenchmarkResult(
                name="Memory Usage",
                duration_ms=duration_ms,
                memory_mb=max_memory,
                cpu_percent=0,  # Not measured here
                success=True,
                target_met=max_memory <= self.targets.memory_limit_mb,
                target_ms=None,
                metadata={"max_memory_mb": max_memory, "avg_memory_mb": avg_memory}
            )
            self.results.append(result)
            
        except Exception as e:
            self._memory_monitor_active = False
            monitor_thread.join()
            raise e
    
    def _benchmark_performance_regression(self):
        """Detect performance regressions by comparing with baseline."""
        print("📊 Checking for performance regressions...")
        
        # Load baseline performance data if available
        baseline_file = self.project_root / "test" / "performance" / "baseline.json"
        if baseline_file.exists():
            with open(baseline_file) as f:
                baseline_data = json.load(f)
            
            # Compare current results with baseline
            for result in self.results:
                baseline_duration = baseline_data.get(result.name, {}).get("duration_ms")
                if baseline_duration:
                    regression_threshold = baseline_duration * 1.2  # 20% regression threshold
                    if result.duration_ms > regression_threshold:
                        print(f"⚠️  Performance regression detected in {result.name}")
                        print(f"   Current: {result.duration_ms:.0f}ms, Baseline: {baseline_duration:.0f}ms")
                        result.metadata = result.metadata or {}
                        result.metadata["regression_detected"] = True
                        result.metadata["baseline_ms"] = baseline_duration
        else:
            print("📝 No baseline data found - creating baseline from current results")
            self._save_baseline_data()
    
    def _save_baseline_data(self):
        """Save current performance data as baseline."""
        baseline_dir = self.project_root / "test" / "performance"
        baseline_dir.mkdir(exist_ok=True)
        
        baseline_data = {}
        for result in self.results:
            baseline_data[result.name] = {
                "duration_ms": result.duration_ms,
                "memory_mb": result.memory_mb,
                "timestamp": time.time()
            }
        
        baseline_file = baseline_dir / "baseline.json"
        with open(baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)
    
    def _run_benchmark(self, name: str, func, target_ms: Optional[float] = None, iterations: int = 1) -> BenchmarkResult:
        """Run a single benchmark with timing and resource monitoring."""
        print(f"  Running {name}...")
        
        durations = []
        memory_usages = []
        cpu_usages = []
        
        for i in range(iterations):
            # Clean before each iteration
            if iterations > 1:
                subprocess.run(["buck2", "clean"], capture_output=True)
            
            # Monitor resources
            process = psutil.Process()
            start_memory = process.memory_info().rss / 1024 / 1024  # MB
            start_cpu = process.cpu_percent()
            
            # Run benchmark
            start_time = time.time()
            try:
                func()
                success = True
            except Exception as e:
                print(f"    ✗ Iteration {i+1} failed: {e}")
                success = False
                duration_ms = (time.time() - start_time) * 1000
                durations.append(duration_ms)
                continue
            
            end_time = time.time()
            duration_ms = (end_time - start_time) * 1000
            
            # Measure resources after
            end_memory = process.memory_info().rss / 1024 / 1024  # MB
            end_cpu = process.cpu_percent()
            
            durations.append(duration_ms)
            memory_usages.append(end_memory - start_memory)
            cpu_usages.append(max(start_cpu, end_cpu))
            
            if iterations > 1:
                print(f"    Iteration {i+1}: {duration_ms:.0f}ms")
        
        if not durations:
            return BenchmarkResult(
                name=name,
                duration_ms=float('inf'),
                memory_mb=0,
                cpu_percent=0,
                success=False,
                target_met=False,
                target_ms=target_ms,
                iterations=iterations
            )
        
        # Calculate statistics
        avg_duration = statistics.mean(durations)
        avg_memory = statistics.mean(memory_usages) if memory_usages else 0
        avg_cpu = statistics.mean(cpu_usages) if cpu_usages else 0
        
        target_met = target_ms is None or avg_duration <= target_ms
        
        result = BenchmarkResult(
            name=name,
            duration_ms=avg_duration,
            memory_mb=avg_memory,
            cpu_percent=avg_cpu,
            success=success,
            target_met=target_met,
            target_ms=target_ms,
            iterations=iterations,
            metadata={
                "min_duration_ms": min(durations),
                "max_duration_ms": max(durations),
                "std_dev_ms": statistics.stdev(durations) if len(durations) > 1 else 0
            }
        )
        
        status = "✓" if target_met else "✗"
        target_info = f" (target: {target_ms}ms)" if target_ms else ""
        print(f"    {status} {name}: {avg_duration:.0f}ms{target_info}")
        
        return result
    
    def _build_target(self, target: str) -> bool:
        """Build a single Buck2 target."""
        result = subprocess.run(
            ["buck2", "build", target],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    
    def _build_targets(self, targets: List[str]) -> bool:
        """Build multiple Buck2 targets."""
        result = subprocess.run(
            ["buck2", "build"] + targets,
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    
    def _generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report."""
        print("📋 Generating performance report...")
        
        # Calculate overall metrics
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.target_met)
        failed_tests = total_tests - passed_tests
        
        # Performance target analysis
        target_analysis = {}
        for result in self.results:
            if result.target_ms:
                target_analysis[result.name] = {
                    "actual_ms": result.duration_ms,
                    "target_ms": result.target_ms,
                    "performance_ratio": result.duration_ms / result.target_ms,
                    "target_met": result.target_met
                }
        
        # Resource usage analysis
        max_memory = max((r.memory_mb for r in self.results), default=0)
        avg_memory = statistics.mean([r.memory_mb for r in self.results])
        max_cpu = max((r.cpu_percent for r in self.results), default=0)
        
        # Regression analysis
        regressions = [
            r for r in self.results 
            if r.metadata and r.metadata.get("regression_detected")
        ]
        
        report = {
            "timestamp": time.time(),
            "summary": {
                "total_benchmarks": total_tests,
                "targets_met": passed_tests,
                "targets_failed": failed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "max_memory_mb": max_memory,
                "avg_memory_mb": avg_memory,
                "max_cpu_percent": max_cpu,
                "regressions_detected": len(regressions)
            },
            "detailed_results": [asdict(r) for r in self.results],
            "target_analysis": target_analysis,
            "performance_targets": asdict(self.targets),
            "regressions": [r.name for r in regressions],
            "recommendations": self._generate_recommendations()
        }
        
        # Save report
        report_path = self.project_root / "test" / "performance" / "performance_report.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []
        
        # Check for failed targets
        failed_results = [r for r in self.results if not r.target_met]
        for result in failed_results:
            if result.target_ms:
                overage_pct = ((result.duration_ms / result.target_ms) - 1) * 100
                recommendations.append(
                    f"Optimize {result.name}: {overage_pct:.1f}% over target"
                )
        
        # Check for high memory usage
        high_memory_results = [r for r in self.results if r.memory_mb > 500]  # 500MB threshold
        if high_memory_results:
            recommendations.append(
                f"Investigate memory usage in: {', '.join(r.name for r in high_memory_results)}"
            )
        
        # Check for regressions
        regressions = [
            r for r in self.results 
            if r.metadata and r.metadata.get("regression_detected")
        ]
        if regressions:
            recommendations.append(
                f"Address performance regressions in: {', '.join(r.name for r in regressions)}"
            )
        
        return recommendations


def main():
    """Main entry point for performance benchmarks."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    benchmarks = PerformanceBenchmarks(project_root)
    
    print("🚀 Starting comprehensive performance benchmark suite...")
    
    try:
        # Run all benchmarks
        report = benchmarks.run_all_benchmarks()
        
        # Print summary
        summary = report["summary"]
        print("\n📊 Performance Benchmark Summary:")
        print(f"  Total Benchmarks: {summary['total_benchmarks']}")
        print(f"  Targets Met: {summary['targets_met']}")
        print(f"  Targets Failed: {summary['targets_failed']}")
        print(f"  Success Rate: {summary['success_rate']:.1%}")
        print(f"  Max Memory Usage: {summary['max_memory_mb']:.1f}MB")
        print(f"  Regressions Detected: {summary['regressions_detected']}")
        
        # Check if all targets met
        all_targets_met = summary['targets_met'] == summary['total_benchmarks']
        
        if all_targets_met and summary['regressions_detected'] == 0:
            print("\n🎉 All performance targets met!")
            sys.exit(0)
        else:
            print("\n⚠️  Performance targets not met or regressions detected.")
            if report.get("recommendations"):
                print("\nRecommendations:")
                for rec in report["recommendations"]:
                    print(f"  - {rec}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Performance benchmarks failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
