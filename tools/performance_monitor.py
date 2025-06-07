#!/usr/bin/env python3
"""
Real-time performance monitor for protobuf Buck2 integration.

This module provides real-time performance monitoring capabilities
for protobuf builds, including performance regression detection,
alerting, and automated optimization recommendations.
"""

import os
import sys
import time
import json
import psutil
import threading
import subprocess
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from collections import deque
from datetime import datetime, timedelta


@dataclass
class PerformanceThresholds:
    """Performance thresholds for monitoring and alerting."""
    max_build_time_ms: float = 30000  # 30 seconds
    max_memory_mb: float = 1024  # 1GB
    max_cpu_percent: float = 90  # 90% CPU
    min_cache_hit_rate: float = 0.7  # 70% cache hit rate
    max_regression_percent: float = 20  # 20% performance regression
    max_consecutive_failures: int = 3


@dataclass
class PerformanceAlert:
    """Performance alert information."""
    alert_type: str
    severity: str  # "warning", "error", "critical"
    message: str
    timestamp: float
    metric_value: float
    threshold_value: float
    target_name: str = ""
    build_id: str = ""


@dataclass
class PerformanceMetric:
    """Single performance metric measurement."""
    timestamp: float
    target_name: str
    build_id: str
    build_time_ms: float
    memory_peak_mb: float
    cpu_utilization: float
    cache_hit_rate: float
    strategy_used: str
    file_count: int
    language_count: int
    success: bool


class PerformanceDatabase:
    """SQLite database for storing performance metrics."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the performance database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    target_name TEXT NOT NULL,
                    build_id TEXT NOT NULL,
                    build_time_ms REAL NOT NULL,
                    memory_peak_mb REAL NOT NULL,
                    cpu_utilization REAL NOT NULL,
                    cache_hit_rate REAL NOT NULL,
                    strategy_used TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    language_count INTEGER NOT NULL,
                    success INTEGER NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS performance_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    alert_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    threshold_value REAL NOT NULL,
                    target_name TEXT,
                    build_id TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_timestamp 
                ON performance_metrics(timestamp)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_target 
                ON performance_metrics(target_name)
            """)
    
    def store_metric(self, metric: PerformanceMetric):
        """Store a performance metric in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO performance_metrics 
                (timestamp, target_name, build_id, build_time_ms, memory_peak_mb,
                 cpu_utilization, cache_hit_rate, strategy_used, file_count,
                 language_count, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metric.timestamp,
                metric.target_name,
                metric.build_id,
                metric.build_time_ms,
                metric.memory_peak_mb,
                metric.cpu_utilization,
                metric.cache_hit_rate,
                metric.strategy_used,
                metric.file_count,
                metric.language_count,
                1 if metric.success else 0
            ))
    
    def store_alert(self, alert: PerformanceAlert):
        """Store a performance alert in the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO performance_alerts
                (timestamp, alert_type, severity, message, metric_value,
                 threshold_value, target_name, build_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.timestamp,
                alert.alert_type,
                alert.severity,
                alert.message,
                alert.metric_value,
                alert.threshold_value,
                alert.target_name,
                alert.build_id
            ))
    
    def get_recent_metrics(self, target_name: str, hours: int = 24) -> List[PerformanceMetric]:
        """Get recent performance metrics for a target."""
        cutoff_time = time.time() - (hours * 3600)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT timestamp, target_name, build_id, build_time_ms,
                       memory_peak_mb, cpu_utilization, cache_hit_rate,
                       strategy_used, file_count, language_count, success
                FROM performance_metrics
                WHERE target_name = ? AND timestamp > ?
                ORDER BY timestamp DESC
            """, (target_name, cutoff_time))
            
            metrics = []
            for row in cursor.fetchall():
                metric = PerformanceMetric(
                    timestamp=row[0],
                    target_name=row[1],
                    build_id=row[2],
                    build_time_ms=row[3],
                    memory_peak_mb=row[4],
                    cpu_utilization=row[5],
                    cache_hit_rate=row[6],
                    strategy_used=row[7],
                    file_count=row[8],
                    language_count=row[9],
                    success=bool(row[10])
                )
                metrics.append(metric)
            
            return metrics
    
    def get_baseline_metrics(self, target_name: str, days: int = 7) -> Dict[str, float]:
        """Get baseline performance metrics for a target."""
        cutoff_time = time.time() - (days * 24 * 3600)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT AVG(build_time_ms), AVG(memory_peak_mb), 
                       AVG(cpu_utilization), AVG(cache_hit_rate)
                FROM performance_metrics
                WHERE target_name = ? AND timestamp > ? AND success = 1
            """, (target_name, cutoff_time))
            
            row = cursor.fetchone()
            if row and row[0] is not None:
                return {
                    "avg_build_time_ms": row[0],
                    "avg_memory_mb": row[1],
                    "avg_cpu_utilization": row[2],
                    "avg_cache_hit_rate": row[3]
                }
            
            return {}


class PerformanceMonitor:
    """Real-time performance monitor for protobuf builds."""
    
    def __init__(self, 
                 db_path: str = "performance_monitoring.db",
                 thresholds: Optional[PerformanceThresholds] = None):
        self.db = PerformanceDatabase(db_path)
        self.thresholds = thresholds or PerformanceThresholds()
        
        # In-memory metrics for real-time monitoring
        self.recent_metrics = deque(maxlen=100)
        self.active_alerts = []
        
        # Background monitoring
        self._monitoring_active = False
        self._monitor_thread = None
        
        # Performance regression tracking
        self._regression_tracker = {}
        
    def start_monitoring(self):
        """Start background performance monitoring."""
        if self._monitoring_active:
            return
        
        self._monitoring_active = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        
        print("🔍 Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop background performance monitoring."""
        self._monitoring_active = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        
        print("⏹️  Performance monitoring stopped")
    
    def record_build_performance(self, 
                                target_name: str,
                                build_id: str,
                                build_time_ms: float,
                                memory_peak_mb: float,
                                cpu_utilization: float,
                                cache_hit_rate: float,
                                strategy_used: str,
                                file_count: int,
                                language_count: int,
                                success: bool = True):
        """Record performance metrics for a build."""
        metric = PerformanceMetric(
            timestamp=time.time(),
            target_name=target_name,
            build_id=build_id,
            build_time_ms=build_time_ms,
            memory_peak_mb=memory_peak_mb,
            cpu_utilization=cpu_utilization,
            cache_hit_rate=cache_hit_rate,
            strategy_used=strategy_used,
            file_count=file_count,
            language_count=language_count,
            success=success
        )
        
        # Store in database
        self.db.store_metric(metric)
        
        # Add to recent metrics
        self.recent_metrics.append(metric)
        
        # Check for performance issues
        self._check_performance_thresholds(metric)
        self._check_performance_regression(metric)
        
        return metric
    
    def get_performance_status(self, target_name: Optional[str] = None) -> Dict[str, Any]:
        """Get current performance status."""
        recent_metrics = list(self.recent_metrics)
        
        if target_name:
            recent_metrics = [m for m in recent_metrics if m.target_name == target_name]
        
        if not recent_metrics:
            return {"status": "no_data", "metrics": []}
        
        # Calculate current status
        recent_build_times = [m.build_time_ms for m in recent_metrics[-10:]]
        recent_memory = [m.memory_peak_mb for m in recent_metrics[-10:]]
        recent_cache_rates = [m.cache_hit_rate for m in recent_metrics[-10:]]
        
        avg_build_time = sum(recent_build_times) / len(recent_build_times)
        avg_memory = sum(recent_memory) / len(recent_memory)
        avg_cache_rate = sum(recent_cache_rates) / len(recent_cache_rates)
        
        # Determine status
        status = "healthy"
        issues = []
        
        if avg_build_time > self.thresholds.max_build_time_ms:
            status = "warning"
            issues.append(f"Build time {avg_build_time:.0f}ms exceeds threshold")
        
        if avg_memory > self.thresholds.max_memory_mb:
            status = "warning"
            issues.append(f"Memory usage {avg_memory:.0f}MB exceeds threshold")
        
        if avg_cache_rate < self.thresholds.min_cache_hit_rate:
            status = "warning"
            issues.append(f"Cache hit rate {avg_cache_rate:.1%} below threshold")
        
        active_alerts = [a for a in self.active_alerts if a.severity in ["error", "critical"]]
        if active_alerts:
            status = "critical"
        
        return {
            "status": status,
            "avg_build_time_ms": avg_build_time,
            "avg_memory_mb": avg_memory,
            "avg_cache_hit_rate": avg_cache_rate,
            "active_alerts": len(self.active_alerts),
            "issues": issues,
            "recent_builds": len(recent_metrics)
        }
    
    def get_performance_recommendations(self, target_name: str) -> List[str]:
        """Get performance optimization recommendations for a target."""
        recommendations = []
        
        # Get recent metrics for target
        recent_metrics = self.db.get_recent_metrics(target_name, hours=24)
        
        if not recent_metrics:
            return ["Insufficient data for recommendations"]
        
        # Analyze patterns
        build_times = [m.build_time_ms for m in recent_metrics if m.success]
        memory_usage = [m.memory_peak_mb for m in recent_metrics if m.success]
        cache_rates = [m.cache_hit_rate for m in recent_metrics if m.success]
        
        if not build_times:
            return ["No successful builds found for analysis"]
        
        avg_build_time = sum(build_times) / len(build_times)
        avg_memory = sum(memory_usage) / len(memory_usage)
        avg_cache_rate = sum(cache_rates) / len(cache_rates)
        
        # Generate recommendations
        if avg_build_time > self.thresholds.max_build_time_ms:
            recommendations.append("Consider enabling parallel compilation for faster builds")
            recommendations.append("Review proto file dependencies to optimize compilation order")
        
        if avg_memory > self.thresholds.max_memory_mb:
            recommendations.append("Enable memory optimization to reduce peak memory usage")
            recommendations.append("Consider processing proto files in smaller batches")
        
        if avg_cache_rate < self.thresholds.min_cache_hit_rate:
            recommendations.append("Investigate cache invalidation patterns")
            recommendations.append("Review cache configuration and storage limits")
        
        # Strategy recommendations
        strategies_used = [m.strategy_used for m in recent_metrics]
        if strategies_used:
            most_common_strategy = max(set(strategies_used), key=strategies_used.count)
            if most_common_strategy == "sequential" and len(recent_metrics) > 5:
                recommendations.append("Consider switching to parallel compilation strategy")
        
        if not recommendations:
            recommendations.append("Performance is within acceptable thresholds")
        
        return recommendations
    
    def generate_performance_report(self, hours: int = 24) -> str:
        """Generate a comprehensive performance report."""
        cutoff_time = time.time() - (hours * 3600)
        
        # Get all recent metrics
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT target_name, COUNT(*), AVG(build_time_ms), AVG(memory_peak_mb),
                       AVG(cache_hit_rate), MAX(build_time_ms), MAX(memory_peak_mb)
                FROM performance_metrics
                WHERE timestamp > ? AND success = 1
                GROUP BY target_name
                ORDER BY AVG(build_time_ms) DESC
            """, (cutoff_time,))
            
            target_stats = cursor.fetchall()
        
        # Get alerts
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*), severity
                FROM performance_alerts
                WHERE timestamp > ?
                GROUP BY severity
            """, (cutoff_time))
            
            alert_stats = dict(cursor.fetchall())
        
        # Generate report
        report = []
        report.append("# Performance Report")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Time Period: Last {hours} hours")
        report.append("")
        
        # Summary
        total_builds = sum(stats[1] for stats in target_stats)
        if total_builds > 0:
            avg_build_time = sum(stats[2] * stats[1] for stats in target_stats) / total_builds
            avg_memory = sum(stats[3] * stats[1] for stats in target_stats) / total_builds
            avg_cache_rate = sum(stats[4] * stats[1] for stats in target_stats) / total_builds
            
            report.append("## Summary")
            report.append(f"- Total Builds: {total_builds}")
            report.append(f"- Average Build Time: {avg_build_time:.0f}ms")
            report.append(f"- Average Memory Usage: {avg_memory:.1f}MB")
            report.append(f"- Average Cache Hit Rate: {avg_cache_rate:.1%}")
            report.append("")
        
        # Alerts
        if alert_stats:
            report.append("## Alerts")
            for severity, count in alert_stats.items():
                report.append(f"- {severity.title()}: {count}")
            report.append("")
        
        # Target Performance
        if target_stats:
            report.append("## Target Performance")
            report.append("| Target | Builds | Avg Time | Peak Time | Avg Memory | Peak Memory | Cache Rate |")
            report.append("|--------|--------|----------|-----------|------------|-------------|------------|")
            
            for stats in target_stats[:20]:  # Top 20 targets
                target_name = stats[0]
                builds = stats[1]
                avg_time = stats[2]
                avg_memory = stats[3]
                cache_rate = stats[4]
                peak_time = stats[5]
                peak_memory = stats[6]
                
                report.append(f"| {target_name} | {builds} | {avg_time:.0f}ms | {peak_time:.0f}ms | {avg_memory:.1f}MB | {peak_memory:.1f}MB | {cache_rate:.1%} |")
            
            report.append("")
        
        # Recommendations
        report.append("## Recommendations")
        if target_stats:
            slowest_target = target_stats[0][0]  # Slowest target
            recommendations = self.get_performance_recommendations(slowest_target)
            for rec in recommendations:
                report.append(f"- {rec}")
        else:
            report.append("- No performance data available for recommendations")
        
        return "\n".join(report)
    
    def _check_performance_thresholds(self, metric: PerformanceMetric):
        """Check if performance metric exceeds thresholds."""
        alerts = []
        
        # Build time threshold
        if metric.build_time_ms > self.thresholds.max_build_time_ms:
            alert = PerformanceAlert(
                alert_type="build_time_exceeded",
                severity="warning",
                message=f"Build time {metric.build_time_ms:.0f}ms exceeds threshold {self.thresholds.max_build_time_ms:.0f}ms",
                timestamp=metric.timestamp,
                metric_value=metric.build_time_ms,
                threshold_value=self.thresholds.max_build_time_ms,
                target_name=metric.target_name,
                build_id=metric.build_id
            )
            alerts.append(alert)
        
        # Memory threshold
        if metric.memory_peak_mb > self.thresholds.max_memory_mb:
            alert = PerformanceAlert(
                alert_type="memory_exceeded",
                severity="warning",
                message=f"Memory usage {metric.memory_peak_mb:.1f}MB exceeds threshold {self.thresholds.max_memory_mb:.1f}MB",
                timestamp=metric.timestamp,
                metric_value=metric.memory_peak_mb,
                threshold_value=self.thresholds.max_memory_mb,
                target_name=metric.target_name,
                build_id=metric.build_id
            )
            alerts.append(alert)
        
        # Cache hit rate threshold
        if metric.cache_hit_rate < self.thresholds.min_cache_hit_rate:
            alert = PerformanceAlert(
                alert_type="cache_hit_rate_low",
                severity="warning",
                message=f"Cache hit rate {metric.cache_hit_rate:.1%} below threshold {self.thresholds.min_cache_hit_rate:.1%}",
                timestamp=metric.timestamp,
                metric_value=metric.cache_hit_rate,
                threshold_value=self.thresholds.min_cache_hit_rate,
                target_name=metric.target_name,
                build_id=metric.build_id
            )
            alerts.append(alert)
        
        # Store and process alerts
        for alert in alerts:
            self.db.store_alert(alert)
            self.active_alerts.append(alert)
            self._process_alert(alert)
    
    def _check_performance_regression(self, metric: PerformanceMetric):
        """Check for performance regression compared to baseline."""
        baseline = self.db.get_baseline_metrics(metric.target_name, days=7)
        
        if not baseline:
            return  # No baseline to compare against
        
        # Check for build time regression
        baseline_time = baseline.get("avg_build_time_ms", 0)
        if baseline_time > 0:
            regression_percent = ((metric.build_time_ms - baseline_time) / baseline_time) * 100
            
            if regression_percent > self.thresholds.max_regression_percent:
                alert = PerformanceAlert(
                    alert_type="performance_regression",
                    severity="error",
                    message=f"Performance regression detected: {regression_percent:.1f}% slower than baseline",
                    timestamp=metric.timestamp,
                    metric_value=metric.build_time_ms,
                    threshold_value=baseline_time * (1 + self.thresholds.max_regression_percent / 100),
                    target_name=metric.target_name,
                    build_id=metric.build_id
                )
                
                self.db.store_alert(alert)
                self.active_alerts.append(alert)
                self._process_alert(alert)
    
    def _process_alert(self, alert: PerformanceAlert):
        """Process a performance alert (logging, notifications, etc.)."""
        severity_emoji = {
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        
        emoji = severity_emoji.get(alert.severity, "ℹ️")
        print(f"{emoji} {alert.severity.upper()}: {alert.message}")
        
        # In a real implementation, this could send notifications,
        # update dashboards, trigger automated responses, etc.
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._monitoring_active:
            try:
                # Clean up old alerts (keep only last hour)
                cutoff_time = time.time() - 3600
                self.active_alerts = [
                    alert for alert in self.active_alerts 
                    if alert.timestamp > cutoff_time
                ]
                
                # System health check
                self._check_system_health()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _check_system_health(self):
        """Check overall system health."""
        try:
            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            if cpu_percent > self.thresholds.max_cpu_percent:
                alert = PerformanceAlert(
                    alert_type="high_cpu_usage",
                    severity="warning",
                    message=f"High CPU usage: {cpu_percent:.1f}%",
                    timestamp=time.time(),
                    metric_value=cpu_percent,
                    threshold_value=self.thresholds.max_cpu_percent
                )
                self.active_alerts.append(alert)
                self._process_alert(alert)
            
            # Check memory usage
            memory = psutil.virtual_memory()
            if memory.percent > 90:  # 90% memory usage
                alert = PerformanceAlert(
                    alert_type="high_memory_usage",
                    severity="warning", 
                    message=f"High system memory usage: {memory.percent:.1f}%",
                    timestamp=time.time(),
                    metric_value=memory.percent,
                    threshold_value=90
                )
                self.active_alerts.append(alert)
                self._process_alert(alert)
        
        except Exception as e:
            print(f"Error checking system health: {e}")


def main():
    """Main entry point for performance monitor."""
    monitor = PerformanceMonitor()
    
    print("🔍 Performance Monitor Ready")
    print("Starting background monitoring...")
    
    monitor.start_monitoring()
    
    try:
        # Example usage
        print("Recording sample performance metrics...")
        
        # Simulate some performance metrics
        for i in range(5):
            monitor.record_build_performance(
                target_name=f"//example:target_{i % 3}",
                build_id=f"build_{int(time.time())}_{i}",
                build_time_ms=1000 + (i * 200),
                memory_peak_mb=100 + (i * 50),
                cpu_utilization=50 + (i * 10),
                cache_hit_rate=0.8 - (i * 0.1),
                strategy_used="concurrent_language",
                file_count=10 + i,
                language_count=2,
                success=True
            )
            time.sleep(1)
        
        # Get status
        status = monitor.get_performance_status()
        print(f"\nCurrent Status: {status['status']}")
        print(f"Average Build Time: {status['avg_build_time_ms']:.0f}ms")
        print(f"Average Memory: {status['avg_memory_mb']:.1f}MB")
        print(f"Cache Hit Rate: {status['avg_cache_hit_rate']:.1%}")
        
        # Get recommendations
        recommendations = monitor.get_performance_recommendations("//example:target_0")
        print(f"\nRecommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
        
        # Generate report
        report = monitor.generate_performance_report(hours=1)
        print(f"\nPerformance Report:")
        print(report)
        
        # Keep running for a bit to demonstrate monitoring
        print("\nMonitoring active... Press Ctrl+C to stop")
        time.sleep(10)
        
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()
