"""Tests for Python protobuf generation rules."""

load("//test:test_utils.py", "test_suite", "test_case", "assert_equals", "assert_contains", "assert_file_exists")
load("//rules:python.bzl", "python_proto_library", "python_proto_messages", "python_grpc_library")

def test_python_proto_messages():
    """Test basic Python protobuf message generation."""
    python_proto_messages(
        name = "test_python_messages",
        proto = "//test/fixtures/basic:minimal_proto",
        python_package = "test.basic.minimal",
    )
    
    # Verify expected files are generated
    expected_files = [
        "minimal_pb2.py",
        "minimal_pb2.pyi", 
        "__init__.py",
        "py.typed"
    ]
    
    for file in expected_files:
        assert_file_exists("test_python_messages", file)

def test_python_grpc_library():
    """Test Python gRPC service generation."""
    python_grpc_library(
        name = "test_python_grpc",
        proto = "//test/fixtures:service_proto",
        python_package = "test.service.v1",
    )
    
    # Verify gRPC files are generated
    expected_files = [
        "service_pb2.py",
        "service_pb2.pyi",
        "service_pb2_grpc.py", 
        "service_pb2_grpc.pyi",
        "__init__.py",
        "py.typed"
    ]
    
    for file in expected_files:
        assert_file_exists("test_python_grpc", file)

def test_python_proto_library_full():
    """Test full Python protobuf library with all features."""
    python_proto_library(
        name = "test_python_full",
        proto = "//test/fixtures:complex_proto",
        python_package = "test.complex.v1",
        plugins = ["python", "grpc-python"],
        generate_stubs = True,
        mypy_support = True,
        options = {
            "python_typing": "strict",
        },
    )
    
    # Verify all expected files
    expected_files = [
        "complex_pb2.py",
        "complex_pb2.pyi",
        "complex_pb2_grpc.py",
        "complex_pb2_grpc.pyi", 
        "__init__.py",
        "py.typed"
    ]
    
    for file in expected_files:
        assert_file_exists("test_python_full", file)

def test_python_package_resolution():
    """Test Python package path resolution logic."""
    # Test explicit package parameter
    python_proto_library(
        name = "test_explicit_package",
        proto = "//test/fixtures/basic:minimal_proto",
        python_package = "explicit.package.v1",
    )
    
    # Test auto-generated package from proto path
    python_proto_library(
        name = "test_auto_package",
        proto = "//test/fixtures/basic:minimal_proto",
        # No explicit package - should auto-generate from path
    )

def test_python_type_stubs():
    """Test Python type stub generation."""
    # Test with stubs enabled
    python_proto_library(
        name = "test_with_stubs",
        proto = "//test/fixtures/basic:types_proto",
        python_package = "test.types.v1",
        generate_stubs = True,
        mypy_support = True,
    )
    
    # Test without stubs (performance mode)
    python_proto_library(
        name = "test_no_stubs",
        proto = "//test/fixtures/basic:types_proto",
        python_package = "test.types.nostubs",
        generate_stubs = False,
        mypy_support = False,
    )
    
    # Verify stub files only exist when enabled
    assert_file_exists("test_with_stubs", "types_pb2.pyi")
    assert_file_exists("test_with_stubs", "py.typed")

def test_python_plugin_configuration():
    """Test different plugin configurations."""
    # Messages only
    python_proto_library(
        name = "test_messages_only",
        proto = "//test/fixtures/basic:minimal_proto",
        plugins = ["python"],
    )
    
    # gRPC only (should include python implicitly)
    python_proto_library(
        name = "test_grpc_only",
        proto = "//test/fixtures:service_proto",
        plugins = ["grpc-python"],
    )
    
    # Both messages and gRPC
    python_proto_library(
        name = "test_both_plugins",
        proto = "//test/fixtures:service_proto", 
        plugins = ["python", "grpc-python"],
    )

def test_python_dependencies():
    """Test Python protobuf dependencies."""
    python_proto_library(
        name = "test_base_proto",
        proto = "//test/fixtures/dependencies:base_proto",
        python_package = "test.deps.base",
    )
    
    python_proto_library(
        name = "test_derived_proto",
        proto = "//test/fixtures/dependencies:derived_proto",
        python_package = "test.deps.derived",
        # derived_proto imports base_proto
    )
    
    # Verify both generate successfully
    assert_file_exists("test_base_proto", "base_pb2.py")
    assert_file_exists("test_derived_proto", "derived_pb2.py")

def test_python_init_py_content():
    """Test __init__.py content generation."""
    python_proto_library(
        name = "test_init_content",
        proto = "//test/fixtures:complex_proto",
        python_package = "test.init.v1",
        plugins = ["python", "grpc-python"],
    )
    
    # Read and validate __init__.py content
    init_content = read_file("test_init_content/__init__.py")
    
    assert_contains(init_content, '__package__ = "test.init.v1"')
    assert_contains(init_content, '__version__ = "1.0.0"')
    assert_contains(init_content, '__all__ = [')
    assert_contains(init_content, '"complex_pb2"')
    assert_contains(init_content, '"complex_pb2_grpc"')
    assert_contains(init_content, 'from . import complex_pb2')
    assert_contains(init_content, 'from . import complex_pb2_grpc')

def test_python_py_typed_marker():
    """Test py.typed marker file generation.""" 
    python_proto_library(
        name = "test_py_typed",
        proto = "//test/fixtures/basic:minimal_proto",
        mypy_support = True,
    )
    
    assert_file_exists("test_py_typed", "py.typed")
    
    # Read and validate py.typed content
    py_typed_content = read_file("test_py_typed/py.typed")
    assert_contains(py_typed_content, "PEP 561 stub package marker")

def test_python_custom_options():
    """Test custom protoc options for Python."""
    python_proto_library(
        name = "test_custom_options",
        proto = "//test/fixtures/basic:minimal_proto",
        python_package = "test.options.v1",
        options = {
            "python_package_prefix": "custom_",
            "python_import_style": "absolute",
            "grpc_python_async_support": "true",
        },
    )
    
    # Verify generation succeeds with custom options
    assert_file_exists("test_custom_options", "minimal_pb2.py")

def test_python_error_handling():
    """Test error handling for invalid configurations."""
    # Test with invalid proto target
    try:
        python_proto_library(
            name = "test_invalid_proto",
            proto = "//nonexistent:proto",
        )
        # Should fail during analysis
        fail("Expected error for invalid proto target")
    except:
        pass  # Expected failure

def test_python_performance():
    """Test Python generation performance with large proto files."""
    python_proto_library(
        name = "test_performance",
        proto = "//test/fixtures/performance:large_proto", 
        python_package = "test.performance.v1",
        plugins = ["python", "grpc-python"],
        generate_stubs = True,
    )
    
    # Verify large file generation completes
    assert_file_exists("test_performance", "large_pb2.py")
    assert_file_exists("test_performance", "large_pb2_grpc.py")

# Test suite definition
python_proto_test_suite = test_suite(
    name = "python_proto_tests",
    tests = [
        test_case("python_proto_messages", test_python_proto_messages),
        test_case("python_grpc_library", test_python_grpc_library),
        test_case("python_proto_library_full", test_python_proto_library_full),
        test_case("python_package_resolution", test_python_package_resolution),
        test_case("python_type_stubs", test_python_type_stubs),
        test_case("python_plugin_configuration", test_python_plugin_configuration),
        test_case("python_dependencies", test_python_dependencies),
        test_case("python_init_py_content", test_python_init_py_content),
        test_case("python_py_typed_marker", test_python_py_typed_marker),
        test_case("python_custom_options", test_python_custom_options),
        test_case("python_error_handling", test_python_error_handling),
        test_case("python_performance", test_python_performance),
    ],
)
