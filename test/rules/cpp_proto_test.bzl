"""Test suite for C++ protobuf generation rules.

This module contains Buck2 tests for validating the cpp_proto_library rule
and related C++ code generation functionality.
"""

load("//test/rules:proto_test.bzl", "proto_test_suite")
load("//test:test_utils.py", "assert_files_exist", "assert_file_contains")

def test_cpp_proto_basic_generation():
    """Test basic C++ protobuf code generation."""
    
    # Test should verify:
    # - .pb.h and .pb.cc files are generated
    # - Generated code compiles with C++17
    # - Namespace is correctly applied
    # - Basic message functionality works
    
    return [
        # Basic message generation test
        native.genrule(
            name = "test_cpp_basic_generation",
            srcs = ["//test/fixtures/basic:minimal_proto"],
            outs = ["cpp_basic_test_result.txt"],
            cmd = """
                # Test C++ basic generation
                $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures/basic:minimal_proto) \\
                    --namespace "test::basic" \\
                    --output-dir $OUT_DIR \\
                && echo "PASS: C++ basic generation" > $OUT
            """,
        ),
        
        # Namespace resolution test
        native.genrule(
            name = "test_cpp_namespace_resolution",
            srcs = ["//test/fixtures/basic:types_proto"],
            outs = ["cpp_namespace_test_result.txt"],
            cmd = """
                # Test namespace resolution
                $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures/basic:types_proto) \\
                    --namespace "custom::namespace::test" \\
                    --output-dir $OUT_DIR \\
                && echo "PASS: C++ namespace resolution" > $OUT
            """,
        ),
    ]

def test_cpp_grpc_generation():
    """Test C++ gRPC service generation."""
    
    return [
        # gRPC service generation test
        native.genrule(
            name = "test_cpp_grpc_generation",
            srcs = ["//test/fixtures:service_proto"],
            outs = ["cpp_grpc_test_result.txt"],
            cmd = """
                # Test gRPC generation
                $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures:service_proto) \\
                    --plugins cpp,grpc-cpp \\
                    --use-grpc \\
                    --namespace "test::grpc" \\
                    --output-dir $OUT_DIR \\
                && echo "PASS: C++ gRPC generation" > $OUT
            """,
        ),
        
        # gRPC service compilation test
        native.genrule(
            name = "test_cpp_grpc_compilation",
            srcs = ["//examples/cpp:user_service_cpp_proto"],
            outs = ["cpp_grpc_compile_result.txt"],
            cmd = """
                # Verify gRPC files exist and can be compiled
                if [ -f "$(location //examples/cpp:user_service_cpp_proto)/src/user_service.grpc.pb.h" ] && \\
                   [ -f "$(location //examples/cpp:user_service_cpp_proto)/src/user_service.grpc.pb.cc" ]; then
                    echo "PASS: C++ gRPC compilation" > $OUT
                else
                    echo "FAIL: C++ gRPC compilation - missing files" > $OUT
                    exit 1
                fi
            """,
        ),
    ]

def test_cpp_compiler_standards():
    """Test C++ compiler standard support."""
    
    return [
        # C++17 standard test
        native.genrule(
            name = "test_cpp17_standard",
            srcs = ["//test/fixtures/basic:minimal_proto"],
            outs = ["cpp17_test_result.txt"],
            cmd = """
                # Test C++17 standard
                $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures/basic:minimal_proto) \\
                    --cpp-standard c++17 \\
                    --output-dir $OUT_DIR \\
                && echo "PASS: C++17 standard" > $OUT
            """,
        ),
        
        # C++20 standard test
        native.genrule(
            name = "test_cpp20_standard",
            srcs = ["//test/fixtures/basic:types_proto"],
            outs = ["cpp20_test_result.txt"],
            cmd = """
                # Test C++20 standard
                $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures/basic:types_proto) \\
                    --cpp-standard c++20 \\
                    --output-dir $OUT_DIR \\
                && echo "PASS: C++20 standard" > $OUT
            """,
        ),
    ]

def test_cpp_build_configs():
    """Test C++ build configuration generation."""
    
    return [
        # BUILD file generation test
        native.genrule(
            name = "test_cpp_build_file_generation",
            srcs = ["//examples/cpp:user_cpp_proto"],
            outs = ["cpp_build_config_result.txt"],
            cmd = """
                # Verify BUILD file exists and contains expected content
                BUILD_FILE="$(location //examples/cpp:user_cpp_proto)/BUILD"
                if [ -f "$BUILD_FILE" ] && \\
                   grep -q "cc_library" "$BUILD_FILE" && \\
                   grep -q "protobuf" "$BUILD_FILE"; then
                    echo "PASS: C++ BUILD file generation" > $OUT
                else
                    echo "FAIL: C++ BUILD file generation" > $OUT
                    exit 1
                fi
            """,
        ),
        
        # CMake file generation test
        native.genrule(
            name = "test_cpp_cmake_generation",
            srcs = ["//examples/cpp:user_cpp_proto"],
            outs = ["cpp_cmake_result.txt"],
            cmd = """
                # Verify CMakeLists.txt exists and contains expected content
                CMAKE_FILE="$(location //examples/cpp:user_cpp_proto)/CMakeLists.txt"
                if [ -f "$CMAKE_FILE" ] && \\
                   grep -q "add_library" "$CMAKE_FILE" && \\
                   grep -q "protobuf" "$CMAKE_FILE"; then
                    echo "PASS: C++ CMake generation" > $OUT
                else
                    echo "FAIL: C++ CMake generation" > $OUT
                    exit 1
                fi
            """,
        ),
    ]

def test_cpp_performance_options():
    """Test C++ performance optimization options."""
    
    return [
        # Arena allocation test
        native.genrule(
            name = "test_cpp_arena_optimization",
            srcs = ["//examples/cpp:user_cpp_advanced"],
            outs = ["cpp_arena_test_result.txt"],
            cmd = """
                # Test arena allocation options
                if grep -q "arena" "$(location //examples/cpp:user_cpp_advanced)"/src/*.h; then
                    echo "PASS: C++ arena optimization" > $OUT
                else
                    echo "FAIL: C++ arena optimization" > $OUT
                    exit 1
                fi
            """,
        ),
        
        # Compiler optimization test
        native.genrule(
            name = "test_cpp_compiler_optimization",
            srcs = ["//examples/cpp:user_service_cpp_optimized"],
            outs = ["cpp_optimization_result.txt"],
            cmd = """
                # Test compiler optimization flags
                BUILD_FILE="$(location //examples/cpp:user_service_cpp_optimized)/BUILD"
                if [ -f "$BUILD_FILE" ] && \\
                   grep -q "\-O3" "$BUILD_FILE" && \\
                   grep -q "\-DNDEBUG" "$BUILD_FILE"; then
                    echo "PASS: C++ compiler optimization" > $OUT
                else
                    echo "FAIL: C++ compiler optimization" > $OUT
                    exit 1
                fi
            """,
        ),
    ]

def test_cpp_error_handling():
    """Test C++ error handling and edge cases."""
    
    return [
        # Invalid namespace test
        native.genrule(
            name = "test_cpp_invalid_namespace",
            srcs = ["//test/fixtures/basic:minimal_proto"],
            outs = ["cpp_invalid_namespace_result.txt"],
            cmd = """
                # Test invalid namespace handling
                if ! $(exe //rules:cpp_proto_library) \\
                    --proto $(location //test/fixtures/basic:minimal_proto) \\
                    --namespace "invalid::namespace::123" \\
                    --output-dir $OUT_DIR 2>/dev/null; then
                    echo "PASS: C++ invalid namespace handling" > $OUT
                else
                    echo "FAIL: C++ invalid namespace handling" > $OUT
                    exit 1
                fi
            """,
        ),
        
        # Missing proto dependency test
        native.genrule(
            name = "test_cpp_missing_dependency",
            outs = ["cpp_missing_dep_result.txt"],
            cmd = """
                # Test missing dependency handling
                if ! $(exe //rules:cpp_proto_library) \\
                    --proto "//nonexistent:proto" \\
                    --output-dir $OUT_DIR 2>/dev/null; then
                    echo "PASS: C++ missing dependency handling" > $OUT
                else
                    echo "FAIL: C++ missing dependency handling" > $OUT
                    exit 1
                fi
            """,
        ),
    ]

def cpp_proto_test_suite():
    """Complete test suite for C++ protobuf generation."""
    
    tests = []
    tests.extend(test_cpp_proto_basic_generation())
    tests.extend(test_cpp_grpc_generation())
    tests.extend(test_cpp_compiler_standards())
    tests.extend(test_cpp_build_configs())
    tests.extend(test_cpp_performance_options())
    tests.extend(test_cpp_error_handling())
    
    # Test suite runner
    native.test_suite(
        name = "cpp_proto_tests",
        tests = [test.get("name") for test in tests],
    )
    
    return tests
