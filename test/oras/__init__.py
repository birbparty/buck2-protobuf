"""
Comprehensive ORAS Integration Testing Suite

This module provides end-to-end testing of ORAS functionality including:
- Integration testing across all ORAS components
- Performance benchmarks with regression detection
- Failure scenario testing with comprehensive error handling
- Security validation and vulnerability testing
- Cross-platform compatibility validation
- Real registry testing against oras.birb.homes

Test Coverage Target: >95% for all ORAS components
Performance Validation: All targets consistently met
Quality Gates: Zero failures, graceful error handling

Usage:
    python -m pytest test/oras/ --cov=tools --cov-report=html
    python -m pytest test/oras/test_performance.py --benchmark
    python test/oras/test_integration.py --real-registry
"""

__version__ = "1.0.0"

# Test configuration
TEST_REGISTRY = "oras.birb.homes"
TEST_NAMESPACE = "buck2-protobuf/test"
TEST_TIMEOUT = 300  # 5 minutes max per test

# Performance targets (from task requirements)
PERFORMANCE_TARGETS = {
    "artifact_pull_50mb": 5.0,  # seconds
    "cache_hit_lookup": 0.1,    # seconds (100ms)
    "content_deduplication": 0.6,  # 60% bandwidth savings
    "parallel_downloads": True,  # should utilize full bandwidth
}

# Coverage requirements
COVERAGE_TARGET = 95.0  # >95% test coverage required

# Test categories
TEST_CATEGORIES = [
    "unit",           # Individual component functionality
    "integration",    # End-to-end workflow validation
    "performance",    # Benchmark validation
    "security",       # Vulnerability and access control
    "failure",        # Error handling and recovery
    "platform",       # Cross-platform compatibility
]
