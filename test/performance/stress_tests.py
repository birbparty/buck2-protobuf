#!/usr/bin/env python3
"""
Stress testing scenarios for protobuf Buck2 integration.

This module provides comprehensive stress testing for performance optimization,
including high-load scenarios, edge cases, and scalability validation.
"""

import os
import sys
import time
import json
import tempfile
import threading
import subprocess
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from test.test_utils import ProtoTestCase, create_test_proto_file, run_command
from tools.performance_profiler import PerformanceProfiler, ProfilingConfig
from tools.performance_monitor import PerformanceMonitor, PerformanceThresholds


@dataclass
class StressTestConfig:
    """Configuration for stress testing scenarios."""
    max_concurrent_builds: int = 20
    max_proto_files: int = 1000
    max_dependency_depth: int = 100
    max_memory_mb: int = 2048
    max_duration_minutes: int = 30
    aggressive_caching: bool = True
    simulate_failures: bool = True
    measure_degradation: bool = True


@dataclass
class StressTestResult:
    """Results from a stress test scenario."""
    scenario_name: str
    success: bool
    duration_seconds: float
    peak_memory_mb: float
    average_cpu_percent: float
    max_concurrent_builds: int
    total_builds_completed: int
    failed_builds: int
    performance_degradation_percent: float
    bottlenecks_identified: List[str]
    recommendations: List[str]
    detailed_metrics: Dict[str, Any]


class StressTestRunner:
    """Comprehensive stress testing runner for protobuf builds."""
    
    def __init__(self, config: Optional[StressTestConfig] = None):
        self.config = config or StressTestConfig()
        self.profiler = PerformanceProfiler(ProfilingConfig(
            output_directory="stress_test_profiles"
        ))
        self.monitor = PerformanceMonitor(
            thresholds=PerformanceThresholds(
                max_build_time_ms=60000,  # Allow longer times for stress tests
                max_memory_mb=self.config.max_memory_mb
            )
        )
        
        self.test_workspace = None
        self.results = []
        
    def run_all_stress_tests(self) -> List[StressTestResult]:
        """Run all stress testing scenarios."""
        print("🚀 Starting comprehensive stress testing...")
        
        self.monitor.start_monitoring()
        
        try:
            # Setup test workspace
            self._setup_test_workspace()
            
            # Core stress test scenarios
            scenarios = [
                ("Concurrent Build Load", self._test_concurrent_build_load),
                ("Large Proto File Sets", self._test_large_proto_file_sets),
                ("Deep Dependency Chains", self._test_deep_dependency_chains),
                ("Memory Pressure", self._test_memory_pressure),
                ("Cache Thrashing", self._test_cache_thrashing),
                ("Multi-Language Stress", self._test_multi_language_stress),
                ("Failure Recovery", self._test_failure_recovery),
                ("Performance Degradation", self._test_performance_degradation),
                ("Resource Exhaustion", self._test_resource_exhaustion),
                ("Scalability Limits", self._test_scalability_limits),
            ]
            
            for scenario_name, test_func in scenarios:
                print(f"\n🔥 Running stress test: {scenario_name}")
                try:
                    result = test_func()
                    result.scenario_name = scenario_name
                    self.results.append(result)
                    
                    if result.success:
                        print(f"  ✅ {scenario_name} completed successfully")
                    else:
                        print(f"  ❌ {scenario_name} failed")
                        
                except Exception as e:
                    print(f"  💥 {scenario_name} crashed: {e}")
                    self.results.append(StressTestResult(
                        scenario_name=scenario_name,
                        success=False,
                        duration_seconds=0,
                        peak_memory_mb=0,
                        average_cpu_percent=0,
                        max_concurrent_builds=0,
                        total_builds_completed=0,
                        failed_builds=0,
                        performance_degradation_percent=0,
                        bottlenecks_identified=[f"Test crashed: {e}"],
                        recommendations=["Fix test implementation"],
                        detailed_metrics={}
                    ))
                
                # Cool down between tests
                time.sleep(5)
            
            # Generate comprehensive report
            self._generate_stress_test_report()
            
            return self.results
            
        finally:
            self.monitor.stop_monitoring()
            self._cleanup_test_workspace()
    
    def _setup_test_workspace(self):
        """Set up isolated test workspace for stress testing."""
        self.test_workspace = Path(tempfile.mkdtemp(prefix="stress_test_"))
        
        # Copy necessary Buck2 files
        import shutil
        for item in ["rules", "tools", "platforms", ".buckconfig"]:
            src = project_root / item
            dst = self.test_workspace / item
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        
        # Create stress test specific directories
        (self.test_workspace / "stress").mkdir()
        (self.test_workspace / "stress" / "large").mkdir()
        (self.test_workspace / "stress" / "deep").mkdir()
        (self.test_workspace / "stress" / "concurrent").mkdir()
        
        os.chdir(self.test_workspace)
        print(f"  Test workspace: {self.test_workspace}")
    
    def _cleanup_test_workspace(self):
        """Clean up test workspace."""
        if self.test_workspace:
            os.chdir(project_root)
            import shutil
            shutil.rmtree(self.test_workspace, ignore_errors=True)
    
    def _test_concurrent_build_load(self) -> StressTestResult:
        """Test system behavior under high concurrent build load."""
        print("  Testing concurrent build load...")
        
        # Create multiple independent proto targets
        targets = []
        for i in range(self.config.max_concurrent_builds):
            proto_content = f"""
syntax = "proto3";

package stress.concurrent.target_{i};

message Message_{i} {{
  string id = 1;
  int32 value = 2;
  repeated string tags = 3;
}}

service Service_{i} {{
  rpc GetMessage(Message_{i}) returns (Message_{i});
}}
"""
            proto_file = self.test_workspace / "stress" / "concurrent" / f"target_{i}.proto"
            proto_file.write_text(proto_content)
            targets.append(f"//stress/concurrent:target_{i}_proto")
        
        # Create BUCK file
        buck_content = ""
        for i in range(self.config.max_concurrent_builds):
            buck_content += f"""
proto_library(
    name = "target_{i}_proto",
    srcs = ["target_{i}.proto"],
    visibility = ["PUBLIC"],
)
"""
        
        buck_file = self.test_workspace / "stress" / "concurrent" / "BUCK"
        buck_file.write_text(buck_content)
        
        # Run concurrent builds
        with self.profiler.profile_execution("concurrent_build_load") as profile:
            start_time = time.time()
            
            # Build all targets concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.max_concurrent_builds) as executor:
                futures = [
                    executor.submit(self._build_target, target)
                    for target in targets
                ]
                
                completed = 0
                failed = 0
                
                for future in concurrent.futures.as_completed(futures):
                    try:
                        success = future.result()
                        if success:
                            completed += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Concurrent Build Load",
            success=failed == 0,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=self.config.max_concurrent_builds,
            total_builds_completed=completed,
            failed_builds=failed,
            performance_degradation_percent=self._calculate_degradation(duration, completed),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("concurrent", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_large_proto_file_sets(self) -> StressTestResult:
        """Test performance with large numbers of proto files."""
        print("  Testing large proto file sets...")
        
        # Generate many proto files
        proto_files = []
        file_count = min(self.config.max_proto_files, 500)  # Limit for test duration
        
        for i in range(file_count):
            proto_content = f"""
syntax = "proto3";

package stress.large.file_{i};

message LargeMessage_{i} {{
  string field_1 = 1;
  int32 field_2 = 2;
  int64 field_3 = 3;
  double field_4 = 4;
  bool field_5 = 5;
  repeated string list_field = 6;
  map<string, string> map_field = 7;
}}
"""
            proto_file = self.test_workspace / "stress" / "large" / f"file_{i}.proto"
            proto_file.write_text(proto_content)
            proto_files.append(f"file_{i}.proto")
        
        # Create BUCK file for large target
        buck_content = f"""
proto_library(
    name = "large_proto_set",
    srcs = {json.dumps(proto_files)},
    visibility = ["PUBLIC"],
)
"""
        
        buck_file = self.test_workspace / "stress" / "large" / "BUCK"
        buck_file.write_text(buck_content)
        
        # Build large proto set
        with self.profiler.profile_execution("large_proto_file_sets") as profile:
            start_time = time.time()
            success = self._build_target("//stress/large:large_proto_set")
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Large Proto File Sets",
            success=success,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=1 if success else 0,
            failed_builds=0 if success else 1,
            performance_degradation_percent=self._calculate_degradation(duration, file_count),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("large_files", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_deep_dependency_chains(self) -> StressTestResult:
        """Test performance with deep dependency chains."""
        print("  Testing deep dependency chains...")
        
        depth = min(self.config.max_dependency_depth, 50)  # Limit for test duration
        
        # Create dependency chain
        for i in range(depth):
            if i == 0:
                # Base proto
                proto_content = """
syntax = "proto3";

package stress.deep.base;

message BaseMessage {
  string id = 1;
  string name = 2;
}
"""
            else:
                # Dependent proto
                import_path = f"stress/deep/level_{i-1}.proto" if i > 1 else "stress/deep/base.proto"
                prev_pkg = f"stress.deep.level_{i-1}" if i > 1 else "stress.deep.base"
                prev_msg = f"Level{i-1}Message" if i > 1 else "BaseMessage"
                
                proto_content = f"""
syntax = "proto3";

package stress.deep.level_{i};

import "{import_path}";

message Level{i}Message {{
  string level_{i}_field = 1;
  {prev_pkg}.{prev_msg} parent = 2;
}}
"""
            
            filename = f"level_{i}.proto" if i > 0 else "base.proto"
            proto_file = self.test_workspace / "stress" / "deep" / filename
            proto_file.write_text(proto_content)
        
        # Create BUCK file with dependency chain
        buck_content = """
proto_library(
    name = "base_proto",
    srcs = ["base.proto"],
    visibility = ["PUBLIC"],
)
"""
        
        for i in range(1, depth):
            deps = ["//stress/deep:base_proto"] if i == 1 else [f"//stress/deep:level_{i-1}_proto"]
            deps_str = json.dumps(deps)
            
            buck_content += f"""
proto_library(
    name = "level_{i}_proto",
    srcs = ["level_{i}.proto"],
    deps = {deps_str},
    visibility = ["PUBLIC"],
)
"""
        
        buck_file = self.test_workspace / "stress" / "deep" / "BUCK"
        buck_file.write_text(buck_content)
        
        # Build deepest target
        with self.profiler.profile_execution("deep_dependency_chains") as profile:
            start_time = time.time()
            success = self._build_target(f"//stress/deep:level_{depth-1}_proto")
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Deep Dependency Chains",
            success=success,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=1 if success else 0,
            failed_builds=0 if success else 1,
            performance_degradation_percent=self._calculate_degradation(duration, depth),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("deep_deps", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_memory_pressure(self) -> StressTestResult:
        """Test system behavior under memory pressure."""
        print("  Testing memory pressure scenarios...")
        
        # Create memory-intensive proto files
        large_proto_content = """
syntax = "proto3";

package stress.memory;

message LargeMessage {
"""
        
        # Add many fields to create large proto
        for i in range(1000):
            field_type = ["string", "int32", "int64", "double", "bool"][i % 5]
            large_proto_content += f"  {field_type} field_{i} = {i + 1};\n"
        
        large_proto_content += """
  repeated string large_repeated_field = 1001;
  map<string, string> large_map_field = 1002;
}

service LargeService {
"""
        
        # Add many service methods
        for i in range(100):
            large_proto_content += f"  rpc Method_{i}(LargeMessage) returns (LargeMessage);\n"
        
        large_proto_content += "}\n"
        
        proto_file = self.test_workspace / "stress" / "memory_pressure.proto"
        proto_file.write_text(large_proto_content)
        
        # Create BUCK file
        buck_content = """
load("//rules:proto.bzl", "proto_library")
load("//rules:go.bzl", "go_proto_library")
load("//rules:python.bzl", "python_proto_library")

proto_library(
    name = "memory_pressure_proto",
    srcs = ["memory_pressure.proto"],
    visibility = ["PUBLIC"],
)

# Generate for multiple languages to increase memory pressure
go_proto_library(
    name = "memory_pressure_go",
    proto = ":memory_pressure_proto",
)

python_proto_library(
    name = "memory_pressure_python",
    proto = ":memory_pressure_proto",
)
"""
        
        buck_file = self.test_workspace / "stress" / "BUCK"
        buck_file.write_text(buck_content)
        
        # Build with memory monitoring
        with self.profiler.profile_execution("memory_pressure") as profile:
            start_time = time.time()
            
            # Build multiple targets to increase memory pressure
            targets = [
                "//stress:memory_pressure_proto",
                "//stress:memory_pressure_go", 
                "//stress:memory_pressure_python"
            ]
            
            success_count = 0
            for target in targets:
                if self._build_target(target):
                    success_count += 1
            
            duration = time.time() - start_time
        
        success = success_count == len(targets)
        
        return StressTestResult(
            scenario_name="Memory Pressure",
            success=success,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=success_count,
            failed_builds=len(targets) - success_count,
            performance_degradation_percent=self._calculate_degradation(duration, 1),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("memory", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_cache_thrashing(self) -> StressTestResult:
        """Test cache behavior under thrashing conditions."""
        print("  Testing cache thrashing scenarios...")
        
        # This test would involve rapidly changing inputs to cause cache misses
        # For now, we'll simulate it with multiple similar targets
        
        with self.profiler.profile_execution("cache_thrashing") as profile:
            start_time = time.time()
            
            # Simulate cache thrashing by building many similar targets
            success_count = 0
            for i in range(20):
                # Build, clean, rebuild pattern to stress cache
                target = f"//stress/concurrent:target_{i % 5}_proto"
                if self._build_target(target):
                    success_count += 1
                
                # Clean to force cache misses
                subprocess.run(["buck2", "clean"], capture_output=True)
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Cache Thrashing",
            success=success_count > 15,  # Allow some failures
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=success_count,
            failed_builds=20 - success_count,
            performance_degradation_percent=self._calculate_degradation(duration, 20),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("cache", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_multi_language_stress(self) -> StressTestResult:
        """Test multi-language generation under stress."""
        print("  Testing multi-language stress scenarios...")
        
        # Create proto for all languages
        proto_content = """
syntax = "proto3";

package stress.multilang;

message MultiLangMessage {
  string id = 1;
  int32 value = 2;
  repeated string items = 3;
  map<string, string> metadata = 4;
}

service MultiLangService {
  rpc Process(MultiLangMessage) returns (MultiLangMessage);
  rpc Stream(MultiLangMessage) returns (stream MultiLangMessage);
}
"""
        
        proto_file = self.test_workspace / "stress" / "multilang.proto"
        proto_file.write_text(proto_content)
        
        # Create BUCK file with all language targets
        buck_content = """
load("//rules:proto.bzl", "proto_library")
load("//rules:go.bzl", "go_proto_library")
load("//rules:python.bzl", "python_proto_library")
load("//rules:typescript.bzl", "typescript_proto_library")
load("//rules:cpp.bzl", "cpp_proto_library")
load("//rules:rust.bzl", "rust_proto_library")

proto_library(
    name = "multilang_proto",
    srcs = ["multilang.proto"],
    visibility = ["PUBLIC"],
)

go_proto_library(
    name = "multilang_go",
    proto = ":multilang_proto",
)

python_proto_library(
    name = "multilang_python", 
    proto = ":multilang_proto",
)

typescript_proto_library(
    name = "multilang_typescript",
    proto = ":multilang_proto",
)

cpp_proto_library(
    name = "multilang_cpp",
    proto = ":multilang_proto",
)

rust_proto_library(
    name = "multilang_rust",
    proto = ":multilang_proto",
)
"""
        
        buck_file = self.test_workspace / "stress" / "BUCK" 
        buck_file.write_text(buck_content)
        
        # Build all language targets
        with self.profiler.profile_execution("multi_language_stress") as profile:
            start_time = time.time()
            
            targets = [
                "//stress:multilang_go",
                "//stress:multilang_python", 
                "//stress:multilang_typescript",
                "//stress:multilang_cpp",
                "//stress:multilang_rust"
            ]
            
            success_count = 0
            for target in targets:
                if self._build_target(target):
                    success_count += 1
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Multi-Language Stress",
            success=success_count >= 3,  # Allow some language failures
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=success_count,
            failed_builds=len(targets) - success_count,
            performance_degradation_percent=self._calculate_degradation(duration, len(targets)),
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("multilang", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_failure_recovery(self) -> StressTestResult:
        """Test system recovery from failures."""
        print("  Testing failure recovery scenarios...")
        
        # This would test recovery from various failure modes
        # For now, simulate with a simple test
        
        with self.profiler.profile_execution("failure_recovery") as profile:
            start_time = time.time()
            
            # Simulate recovery by building valid targets after invalid ones
            success_count = 0
            try:
                # Try to build non-existent target (should fail)
                self._build_target("//stress:nonexistent")
            except:
                pass
            
            # Build valid targets (should succeed)
            if self._build_target("//stress/concurrent:target_0_proto"):
                success_count += 1
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Failure Recovery",
            success=success_count > 0,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=success_count,
            failed_builds=1,
            performance_degradation_percent=0,
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("recovery", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_performance_degradation(self) -> StressTestResult:
        """Test for performance degradation over time."""
        print("  Testing performance degradation...")
        
        # Build same target multiple times and measure degradation
        target = "//stress/concurrent:target_0_proto"
        build_times = []
        
        with self.profiler.profile_execution("performance_degradation") as profile:
            start_time = time.time()
            
            for i in range(10):
                build_start = time.time()
                success = self._build_target(target)
                build_end = time.time()
                
                if success:
                    build_times.append(build_end - build_start)
                
                # Clean between builds
                subprocess.run(["buck2", "clean"], capture_output=True)
            
            duration = time.time() - start_time
        
        # Calculate degradation
        degradation = 0
        if len(build_times) >= 2:
            first_build = build_times[0]
            last_build = build_times[-1]
            degradation = ((last_build - first_build) / first_build) * 100
        
        return StressTestResult(
            scenario_name="Performance Degradation",
            success=len(build_times) >= 8,  # Most builds should succeed
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=len(build_times),
            failed_builds=10 - len(build_times),
            performance_degradation_percent=degradation,
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("degradation", profile),
            detailed_metrics={"build_times": build_times}
        )
    
    def _test_resource_exhaustion(self) -> StressTestResult:
        """Test behavior under resource exhaustion."""
        print("  Testing resource exhaustion scenarios...")
        
        # This is a placeholder - real implementation would stress system resources
        with self.profiler.profile_execution("resource_exhaustion") as profile:
            start_time = time.time()
            
            # Simulate resource stress
            success = self._build_target("//stress:multilang_proto")
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Resource Exhaustion",
            success=success,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=1,
            total_builds_completed=1 if success else 0,
            failed_builds=0 if success else 1,
            performance_degradation_percent=0,
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("resources", profile),
            detailed_metrics=profile.system_metrics or {}
        )
    
    def _test_scalability_limits(self) -> StressTestResult:
        """Test scalability limits of the system."""
        print("  Testing scalability limits...")
        
        # Test with increasing load until failure
        max_successful = 0
        
        with self.profiler.profile_execution("scalability_limits") as profile:
            start_time = time.time()
            
            # Try building increasing numbers of targets
            for batch_size in [1, 5, 10, 20]:
                targets = [f"//stress/concurrent:target_{i}_proto" for i in range(batch_size)]
                
                try:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=batch_size) as executor:
                        futures = [executor.submit(self._build_target, target) for target in targets]
                        results = [f.result() for f in futures]
                        
                        if all(results):
                            max_successful = batch_size
                        else:
                            break
                except Exception:
                    break
            
            duration = time.time() - start_time
        
        return StressTestResult(
            scenario_name="Scalability Limits",
            success=max_successful >= 10,
            duration_seconds=duration,
            peak_memory_mb=profile.peak_memory_mb,
            average_cpu_percent=profile.average_cpu_percent,
            max_concurrent_builds=max_successful,
            total_builds_completed=max_successful,
            failed_builds=0,
            performance_degradation_percent=0,
            bottlenecks_identified=self._identify_bottlenecks(profile),
            recommendations=self._generate_recommendations("scalability", profile),
            detailed_metrics={"max_successful_concurrent": max_successful}
        )
    
    def _build_target(self, target: str) -> bool:
        """Build a Buck2 target."""
        try:
            result = subprocess.run(
                ["buck2", "build", target],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for stress tests
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _calculate_degradation(self, duration: float, workload_size: int) -> float:
        """Calculate performance degradation percentage."""
        # Simple heuristic: if it takes more than 1 second per unit of work, consider it degraded
        expected_time = workload_size * 0.1  # 100ms per unit
        if expected_time > 0:
            return max(0, ((duration - expected_time) / expected_time) * 100)
        return 0
    
    def _identify_bottlenecks(self, profile) -> List[str]:
        """Identify performance bottlenecks from profile data."""
        bottlenecks = []
        
        if hasattr(profile, 'peak_memory_mb') and profile.peak_memory_mb > 1000:
            bottlenecks.append("High memory usage detected")
        
        if hasattr(profile, 'average_cpu_percent') and profile.average_cpu_percent > 80:
            bottlenecks.append("High CPU utilization detected")
        
        if hasattr(profile, 'duration_seconds') and profile.duration_seconds > 60:
            bottlenecks.append("Long execution time detected")
        
        return bottlenecks
    
    def _generate_recommendations(self, test_type: str, profile) -> List[str]:
        """Generate performance recommendations based on test type and profile."""
        recommendations = []
        
        if test_type == "concurrent":
            if hasattr(profile, 'peak_memory_mb') and profile.peak_memory_mb > 1000:
                recommendations.append("Consider reducing concurrent build limit to manage memory usage")
            recommendations.append("Enable parallel compilation optimization")
            recommendations.append("Optimize cache hit rates for better concurrent performance")
        
        elif test_type == "large_files":
            recommendations.append("Consider batch processing for large proto file sets")
            recommendations.append("Implement streaming I/O for memory optimization")
            recommendations.append("Use dependency analysis to optimize build order")
        
        elif test_type == "deep_deps":
            recommendations.append("Optimize dependency resolution algorithms")
            recommendations.append("Consider flattening deep dependency chains where possible")
            recommendations.append("Implement incremental dependency processing")
        
        elif test_type == "memory":
            recommendations.append("Enable memory optimization features")
            recommendations.append("Implement garbage collection between compilation phases")
            recommendations.append("Use memory-mapped files for large artifacts")
        
        elif test_type == "cache":
            recommendations.append("Review cache configuration and storage limits")
            recommendations.append("Implement cache warming strategies")
            recommendations.append("Optimize cache key generation for better hit rates")
        
        elif test_type == "multilang":
            recommendations.append("Optimize multi-language compilation scheduling")
            recommendations.append("Consider language-specific optimization strategies")
            recommendations.append("Implement shared artifact caching across languages")
        
        elif test_type == "recovery":
            recommendations.append("Implement robust error handling and recovery")
            recommendations.append("Add automatic retry mechanisms for transient failures")
            recommendations.append("Improve error reporting and diagnostics")
        
        elif test_type == "degradation":
            recommendations.append("Monitor for memory leaks and resource accumulation")
            recommendations.append("Implement periodic cleanup and optimization")
            recommendations.append("Add performance regression detection")
        
        elif test_type == "resources":
            recommendations.append("Implement resource usage limits and monitoring")
            recommendations.append("Add graceful degradation under resource pressure")
            recommendations.append("Optimize resource allocation algorithms")
        
        elif test_type == "scalability":
            recommendations.append("Identify and address scalability bottlenecks")
            recommendations.append("Implement adaptive load balancing")
            recommendations.append("Consider horizontal scaling strategies")
        
        if not recommendations:
            recommendations.append("No specific recommendations for this test type")
        
        return recommendations
    
    def _generate_stress_test_report(self):
        """Generate comprehensive stress test report."""
        report = []
        report.append("# Stress Test Report")
        report.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Configuration: {asdict(self.config)}")
        report.append("")
        
        # Summary
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success)
        failed_tests = total_tests - passed_tests
        
        report.append("## Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- Passed: {passed_tests}")
        report.append(f"- Failed: {failed_tests}")
        report.append(f"- Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "- Success Rate: 0%")
        report.append("")
        
        # Detailed Results
        report.append("## Detailed Results")
        report.append("| Scenario | Success | Duration | Peak Memory | Concurrent | Completed | Failed | Degradation |")
        report.append("|----------|---------|----------|-------------|------------|-----------|--------|-------------|")
        
        for result in self.results:
            status = "✅" if result.success else "❌"
            report.append(f"| {result.scenario_name} | {status} | {result.duration_seconds:.1f}s | {result.peak_memory_mb:.1f}MB | {result.max_concurrent_builds} | {result.total_builds_completed} | {result.failed_builds} | {result.performance_degradation_percent:.1f}% |")
        
        report.append("")
        
        # Bottlenecks and Recommendations
        report.append("## Identified Bottlenecks")
        all_bottlenecks = []
        for result in self.results:
            all_bottlenecks.extend(result.bottlenecks_identified)
        
        unique_bottlenecks = list(set(all_bottlenecks))
        for bottleneck in unique_bottlenecks:
            report.append(f"- {bottleneck}")
        
        report.append("")
        report.append("## Recommendations")
        all_recommendations = []
        for result in self.results:
            all_recommendations.extend(result.recommendations)
        
        unique_recommendations = list(set(all_recommendations))
        for rec in unique_recommendations:
            report.append(f"- {rec}")
        
        # Save report
        report_path = Path("stress_test_report.md")
        report_path.write_text("\n".join(report))
        print(f"📋 Stress test report saved: {report_path}")


def main():
    """Main entry point for stress testing."""
    config = StressTestConfig(
        max_concurrent_builds=10,  # Reduce for testing
        max_proto_files=100,       # Reduce for testing
        max_dependency_depth=20,   # Reduce for testing
    )
    
    runner = StressTestRunner(config)
    
    print("🔥 Starting protobuf stress testing suite...")
    
    try:
        results = runner.run_all_stress_tests()
        
        # Print summary
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.success)
        
        print(f"\n📊 Stress Test Summary:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {total_tests - passed_tests}")
        print(f"  Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "  Success Rate: 0%")
        
        # Show failed tests
        failed_tests = [r for r in results if not r.success]
        if failed_tests:
            print("\n❌ Failed Tests:")
            for test in failed_tests:
                print(f"  - {test.scenario_name}")
                for bottleneck in test.bottlenecks_identified:
                    print(f"    • {bottleneck}")
        
        return 0 if passed_tests == total_tests else 1
        
    except Exception as e:
        print(f"\n💥 Stress testing failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
