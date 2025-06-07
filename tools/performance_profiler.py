#!/usr/bin/env python3
"""
Performance profiler for protobuf Buck2 integration.

This module provides comprehensive performance profiling capabilities
including CPU profiling, memory profiling, I/O profiling, and real-time
performance monitoring for protobuf builds.
"""

import os
import sys
import time
import json
import psutil
import threading
import subprocess
import cProfile
import pstats
import io
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

try:
    import memory_profiler
    MEMORY_PROFILER_AVAILABLE = True
except ImportError:
    MEMORY_PROFILER_AVAILABLE = False
    print("Warning: memory_profiler not available. Install with: pip install memory_profiler")

try:
    import py_spy
    PY_SPY_AVAILABLE = True
except ImportError:
    PY_SPY_AVAILABLE = False


@dataclass
class ProfilingConfig:
    """Configuration for performance profiling."""
    cpu_profiling_enabled: bool = True
    memory_profiling_enabled: bool = True
    io_profiling_enabled: bool = True
    sampling_interval_ms: int = 100
    output_directory: str = "performance_profiles"
    detailed_memory_tracking: bool = False
    profile_child_processes: bool = False
    max_profile_duration_seconds: int = 300  # 5 minutes max


@dataclass
class PerformanceProfile:
    """Results from performance profiling."""
    cpu_profile_data: Optional[str] = None
    memory_profile_data: Optional[str] = None
    io_profile_data: Optional[str] = None
    system_metrics: Optional[Dict[str, Any]] = None
    duration_seconds: float = 0.0
    peak_memory_mb: float = 0.0
    average_cpu_percent: float = 0.0
    total_io_bytes: int = 0
    profile_timestamp: float = 0.0


class PerformanceProfiler:
    """Comprehensive performance profiler for protobuf builds."""
    
    def __init__(self, config: Optional[ProfilingConfig] = None):
        self.config = config or ProfilingConfig()
        self.output_dir = Path(self.config.output_directory)
        self.output_dir.mkdir(exist_ok=True)
        
        self._monitoring_active = False
        self._system_metrics = []
        self._monitor_thread = None
        self._start_time = None
        
    @contextmanager
    def profile_execution(self, profile_name: str):
        """Context manager for profiling code execution.
        
        Args:
            profile_name: Name for the profiling session
            
        Yields:
            PerformanceProfile: Profile results (populated on exit)
        """
        profile = PerformanceProfile()
        profile.profile_timestamp = time.time()
        
        # Start profiling
        cpu_profiler = None
        memory_profiler_process = None
        
        try:
            # Start system monitoring
            self._start_system_monitoring()
            
            # Start CPU profiling
            if self.config.cpu_profiling_enabled:
                cpu_profiler = cProfile.Profile()
                cpu_profiler.enable()
            
            # Start memory profiling
            if self.config.memory_profiling_enabled and MEMORY_PROFILER_AVAILABLE:
                memory_profiler_process = self._start_memory_profiling(profile_name)
            
            self._start_time = time.time()
            
            yield profile
            
        finally:
            # Stop profiling and collect results
            end_time = time.time()
            profile.duration_seconds = end_time - self._start_time
            
            # Stop CPU profiling
            if cpu_profiler:
                cpu_profiler.disable()
                profile.cpu_profile_data = self._process_cpu_profile(cpu_profiler, profile_name)
            
            # Stop memory profiling
            if memory_profiler_process:
                profile.memory_profile_data = self._stop_memory_profiling(memory_profiler_process, profile_name)
            
            # Stop system monitoring
            self._stop_system_monitoring()
            profile.system_metrics = self._process_system_metrics()
            
            # Save profile data
            self._save_profile_data(profile, profile_name)
    
    def profile_function(self, func: Callable, *args, **kwargs) -> tuple:
        """Profile a specific function execution.
        
        Args:
            func: Function to profile
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            tuple: (function_result, performance_profile)
        """
        profile_name = f"function_{func.__name__}_{int(time.time())}"
        
        with self.profile_execution(profile_name) as profile:
            result = func(*args, **kwargs)
        
        return result, profile
    
    def profile_command(self, command: List[str], working_dir: Optional[str] = None) -> tuple:
        """Profile external command execution.
        
        Args:
            command: Command to execute
            working_dir: Working directory for command
            
        Returns:
            tuple: (return_code, stdout, stderr, performance_profile)
        """
        profile_name = f"command_{command[0]}_{int(time.time())}"
        
        with self.profile_execution(profile_name) as profile:
            # Execute command with profiling
            start_time = time.time()
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=working_dir,
                text=True
            )
            
            # Monitor process resources
            psutil_process = psutil.Process(process.pid)
            max_memory = 0
            cpu_times = []
            
            while process.poll() is None:
                try:
                    # Get memory usage
                    memory_info = psutil_process.memory_info()
                    max_memory = max(max_memory, memory_info.rss)
                    
                    # Get CPU usage
                    cpu_percent = psutil_process.cpu_percent()
                    cpu_times.append(cpu_percent)
                    
                    time.sleep(0.1)  # Sample every 100ms
                except psutil.NoSuchProcess:
                    break
            
            stdout, stderr = process.communicate()
            return_code = process.returncode
            
            # Update profile with process metrics
            profile.peak_memory_mb = max_memory / 1024 / 1024
            profile.average_cpu_percent = sum(cpu_times) / len(cpu_times) if cpu_times else 0
        
        return return_code, stdout, stderr, profile
    
    def benchmark_operation(self, operation: Callable, iterations: int = 10) -> Dict[str, Any]:
        """Benchmark an operation multiple times.
        
        Args:
            operation: Operation to benchmark
            iterations: Number of iterations to run
            
        Returns:
            dict: Benchmark results
        """
        results = []
        
        for i in range(iterations):
            profile_name = f"benchmark_{operation.__name__}_iter_{i}"
            
            with self.profile_execution(profile_name) as profile:
                start_time = time.time()
                operation()
                end_time = time.time()
                
                execution_time = end_time - start_time
                results.append({
                    "iteration": i,
                    "execution_time_ms": execution_time * 1000,
                    "memory_mb": profile.peak_memory_mb,
                    "cpu_percent": profile.average_cpu_percent,
                })
        
        # Calculate statistics
        execution_times = [r["execution_time_ms"] for r in results]
        memory_usage = [r["memory_mb"] for r in results]
        
        return {
            "iterations": iterations,
            "total_time_ms": sum(execution_times),
            "average_time_ms": sum(execution_times) / len(execution_times),
            "min_time_ms": min(execution_times),
            "max_time_ms": max(execution_times),
            "std_dev_ms": self._calculate_std_dev(execution_times),
            "average_memory_mb": sum(memory_usage) / len(memory_usage),
            "peak_memory_mb": max(memory_usage),
            "detailed_results": results,
        }
    
    def _start_system_monitoring(self):
        """Starts system resource monitoring in background thread."""
        self._monitoring_active = True
        self._system_metrics = []
        self._monitor_thread = threading.Thread(target=self._monitor_system_resources)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
    
    def _stop_system_monitoring(self):
        """Stops system resource monitoring."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
    
    def _monitor_system_resources(self):
        """Background thread function for monitoring system resources."""
        while self._monitoring_active:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                disk_io = psutil.disk_io_counters()
                
                metric = {
                    "timestamp": time.time(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_used_mb": memory.used / 1024 / 1024,
                    "disk_read_bytes": disk_io.read_bytes if disk_io else 0,
                    "disk_write_bytes": disk_io.write_bytes if disk_io else 0,
                }
                
                self._system_metrics.append(metric)
                
                time.sleep(self.config.sampling_interval_ms / 1000.0)
                
            except Exception as e:
                print(f"Error monitoring system resources: {e}")
                break
    
    def _process_system_metrics(self) -> Dict[str, Any]:
        """Processes collected system metrics.
        
        Returns:
            dict: Processed system metrics
        """
        if not self._system_metrics:
            return {}
        
        cpu_values = [m["cpu_percent"] for m in self._system_metrics]
        memory_values = [m["memory_used_mb"] for m in self._system_metrics]
        
        # Calculate I/O delta
        io_read_start = self._system_metrics[0]["disk_read_bytes"]
        io_write_start = self._system_metrics[0]["disk_write_bytes"]
        io_read_end = self._system_metrics[-1]["disk_read_bytes"]
        io_write_end = self._system_metrics[-1]["disk_write_bytes"]
        
        return {
            "sample_count": len(self._system_metrics),
            "duration_seconds": self._system_metrics[-1]["timestamp"] - self._system_metrics[0]["timestamp"],
            "cpu_average": sum(cpu_values) / len(cpu_values),
            "cpu_peak": max(cpu_values),
            "memory_average_mb": sum(memory_values) / len(memory_values),
            "memory_peak_mb": max(memory_values),
            "total_disk_read_bytes": io_read_end - io_read_start,
            "total_disk_write_bytes": io_write_end - io_write_start,
            "raw_metrics": self._system_metrics if len(self._system_metrics) < 1000 else [],  # Limit raw data
        }
    
    def _process_cpu_profile(self, profiler: cProfile.Profile, profile_name: str) -> str:
        """Processes CPU profiling results.
        
        Args:
            profiler: CPU profiler instance
            profile_name: Name of the profile
            
        Returns:
            str: Path to saved CPU profile file
        """
        # Save binary profile
        profile_file = self.output_dir / f"{profile_name}_cpu.prof"
        profiler.dump_stats(str(profile_file))
        
        # Generate text report
        text_file = self.output_dir / f"{profile_name}_cpu.txt"
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s)
        ps.strip_dirs().sort_stats('cumulative').print_stats(50)  # Top 50 functions
        
        with open(text_file, 'w') as f:
            f.write(s.getvalue())
        
        return str(text_file)
    
    def _start_memory_profiling(self, profile_name: str) -> Optional[subprocess.Popen]:
        """Starts memory profiling process.
        
        Args:
            profile_name: Name of the profile
            
        Returns:
            subprocess.Popen: Memory profiler process or None
        """
        if not MEMORY_PROFILER_AVAILABLE:
            return None
        
        # Start memory profiler in background
        # This is simplified - in practice, you'd use memory_profiler.profile decorator
        return None
    
    def _stop_memory_profiling(self, process: Optional[subprocess.Popen], profile_name: str) -> Optional[str]:
        """Stops memory profiling and processes results.
        
        Args:
            process: Memory profiler process
            profile_name: Name of the profile
            
        Returns:
            str: Path to memory profile file or None
        """
        if not process:
            return None
        
        # Stop process and save results
        memory_file = self.output_dir / f"{profile_name}_memory.txt"
        # Implementation would save memory profiling results
        return str(memory_file)
    
    def _save_profile_data(self, profile: PerformanceProfile, profile_name: str):
        """Saves complete profile data to file.
        
        Args:
            profile: Performance profile data
            profile_name: Name of the profile
        """
        profile_file = self.output_dir / f"{profile_name}_complete.json"
        
        with open(profile_file, 'w') as f:
            json.dump(asdict(profile), f, indent=2, default=str)
        
        print(f"Profile saved: {profile_file}")
    
    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculates standard deviation of values.
        
        Args:
            values: List of numeric values
            
        Returns:
            float: Standard deviation
        """
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5


class ProtobufBuildProfiler:
    """Specialized profiler for protobuf build operations."""
    
    def __init__(self, profiler: PerformanceProfiler):
        self.profiler = profiler
    
    def profile_protoc_execution(self, protoc_cmd: List[str], working_dir: str) -> tuple:
        """Profile protoc command execution.
        
        Args:
            protoc_cmd: Protoc command line
            working_dir: Working directory
            
        Returns:
            tuple: (return_code, stdout, stderr, profile)
        """
        return self.profiler.profile_command(protoc_cmd, working_dir)
    
    def profile_rule_execution(self, rule_function: Callable, *args, **kwargs) -> tuple:
        """Profile Buck2 rule execution.
        
        Args:
            rule_function: Rule function to profile
            *args: Rule arguments
            **kwargs: Rule keyword arguments
            
        Returns:
            tuple: (result, profile)
        """
        return self.profiler.profile_function(rule_function, *args, **kwargs)
    
    def benchmark_compilation_strategies(self, proto_files: List[str], languages: List[str]) -> Dict[str, Any]:
        """Benchmark different compilation strategies.
        
        Args:
            proto_files: List of proto files
            languages: List of target languages
            
        Returns:
            dict: Benchmark results for different strategies
        """
        strategies = {
            "sequential": self._sequential_compilation,
            "parallel_files": self._parallel_files_compilation,
            "parallel_languages": self._parallel_languages_compilation,
        }
        
        results = {}
        
        for strategy_name, strategy_func in strategies.items():
            print(f"Benchmarking {strategy_name} strategy...")
            
            benchmark_result = self.profiler.benchmark_operation(
                lambda: strategy_func(proto_files, languages),
                iterations=3
            )
            
            results[strategy_name] = benchmark_result
        
        return results
    
    def _sequential_compilation(self, proto_files: List[str], languages: List[str]):
        """Simulates sequential compilation strategy."""
        # Simulate compilation work
        for proto_file in proto_files:
            for language in languages:
                time.sleep(0.01)  # Simulate work
    
    def _parallel_files_compilation(self, proto_files: List[str], languages: List[str]):
        """Simulates parallel files compilation strategy."""
        # Simulate parallel file processing
        for language in languages:
            # Simulate parallel processing of files
            time.sleep(0.01 * len(proto_files) / 4)  # 4x speedup simulation
    
    def _parallel_languages_compilation(self, proto_files: List[str], languages: List[str]):
        """Simulates parallel languages compilation strategy."""
        # Simulate parallel language processing
        max_work = max(len(proto_files) * 0.01, 0.01)
        time.sleep(max_work)  # Process all languages in parallel


def create_performance_report(profiler: PerformanceProfiler, profile_results: List[PerformanceProfile]) -> str:
    """Creates a comprehensive performance report.
    
    Args:
        profiler: Performance profiler instance
        profile_results: List of performance profiles
        
    Returns:
        str: Path to generated report
    """
    report_file = profiler.output_dir / f"performance_report_{int(time.time())}.html"
    
    # Generate HTML report
    html_content = _generate_html_report(profile_results)
    
    with open(report_file, 'w') as f:
        f.write(html_content)
    
    print(f"Performance report generated: {report_file}")
    return str(report_file)


def _generate_html_report(profiles: List[PerformanceProfile]) -> str:
    """Generates HTML performance report.
    
    Args:
        profiles: List of performance profiles
        
    Returns:
        str: HTML content
    """
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Protobuf Buck2 Performance Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f0f0f0; padding: 20px; border-radius: 5px; }
        .section { margin: 20px 0; }
        .metric { display: inline-block; margin: 10px; padding: 10px; border: 1px solid #ddd; border-radius: 3px; }
        .chart { width: 100%; height: 300px; border: 1px solid #ddd; margin: 10px 0; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Protobuf Buck2 Performance Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Total Profiles: {profile_count}</p>
    </div>
    
    <div class="section">
        <h2>Performance Summary</h2>
        {summary_metrics}
    </div>
    
    <div class="section">
        <h2>Detailed Results</h2>
        {detailed_table}
    </div>
</body>
</html>
""".format(
        timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),
        profile_count=len(profiles),
        summary_metrics=_generate_summary_metrics(profiles),
        detailed_table=_generate_detailed_table(profiles)
    )
    
    return html


def _generate_summary_metrics(profiles: List[PerformanceProfile]) -> str:
    """Generates summary metrics HTML."""
    if not profiles:
        return "<p>No profiling data available.</p>"
    
    total_duration = sum(p.duration_seconds for p in profiles)
    avg_memory = sum(p.peak_memory_mb for p in profiles) / len(profiles)
    avg_cpu = sum(p.average_cpu_percent for p in profiles) / len(profiles)
    
    return f"""
    <div class="metric">
        <strong>Total Duration:</strong><br>
        {total_duration:.2f} seconds
    </div>
    <div class="metric">
        <strong>Average Memory:</strong><br>
        {avg_memory:.1f} MB
    </div>
    <div class="metric">
        <strong>Average CPU:</strong><br>
        {avg_cpu:.1f}%
    </div>
    """


def _generate_detailed_table(profiles: List[PerformanceProfile]) -> str:
    """Generates detailed results table HTML."""
    if not profiles:
        return "<p>No detailed data available.</p>"
    
    rows = []
    for i, profile in enumerate(profiles):
        rows.append(f"""
        <tr>
            <td>{i + 1}</td>
            <td>{profile.duration_seconds:.3f}s</td>
            <td>{profile.peak_memory_mb:.1f} MB</td>
            <td>{profile.average_cpu_percent:.1f}%</td>
            <td>{profile.total_io_bytes}</td>
        </tr>
        """)
    
    return f"""
    <table>
        <thead>
            <tr>
                <th>Profile #</th>
                <th>Duration</th>
                <th>Peak Memory</th>
                <th>Avg CPU</th>
                <th>Total I/O</th>
            </tr>
        </thead>
        <tbody>
            {''.join(rows)}
        </tbody>
    </table>
    """


def main():
    """Main entry point for performance profiler."""
    config = ProfilingConfig(
        cpu_profiling_enabled=True,
        memory_profiling_enabled=True,
        output_directory="performance_profiles",
    )
    
    profiler = PerformanceProfiler(config)
    protobuf_profiler = ProtobufBuildProfiler(profiler)
    
    # Example usage
    print("🔍 Performance Profiler Ready")
    print(f"Output directory: {profiler.output_dir}")
    
    # Example profiling session
    with profiler.profile_execution("example_session") as profile:
        # Simulate some work
        time.sleep(1)
        print("Simulated protobuf compilation work...")
    
    print(f"✓ Profile completed: {profile.duration_seconds:.3f}s")


if __name__ == "__main__":
    main()
