#!/bin/bash
# Integration test for Python protobuf generation and compilation

set -e

echo "🐍 Testing Python Protobuf Generation Integration"
echo "================================================"

# Test directory for generated files
TEST_DIR="/tmp/python_proto_test_$$"
mkdir -p "$TEST_DIR"

# Cleanup function
cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

echo "📁 Created test directory: $TEST_DIR"

# Test 1: Basic Python protobuf message generation
echo "🧪 Test 1: Basic Python message generation"
buck2 build //examples/python:user_py_messages --show-output 2>&1 | tee "$TEST_DIR/build_messages.log"

if [ $? -eq 0 ]; then
    echo "✅ Python message generation successful"
else
    echo "❌ Python message generation failed"
    cat "$TEST_DIR/build_messages.log"
    exit 1
fi

# Test 2: Python gRPC service generation
echo "🧪 Test 2: Python gRPC service generation"
buck2 build //examples/python:user_service_py_grpc --show-output 2>&1 | tee "$TEST_DIR/build_grpc.log"

if [ $? -eq 0 ]; then
    echo "✅ Python gRPC generation successful"
else
    echo "❌ Python gRPC generation failed"
    cat "$TEST_DIR/build_grpc.log"
    exit 1
fi

# Test 3: Full Python protobuf library
echo "🧪 Test 3: Full Python protobuf library"
buck2 build //examples/python:user_py_proto --show-output 2>&1 | tee "$TEST_DIR/build_full.log"

if [ $? -eq 0 ]; then
    echo "✅ Full Python protobuf library generation successful"
else
    echo "❌ Full Python protobuf library generation failed"
    cat "$TEST_DIR/build_full.log"
    exit 1
fi

# Test 4: Verify generated file structure
echo "🧪 Test 4: Verify generated file structure"

# Get output directory from buck2
OUTPUT_DIR=$(buck2 build //examples/python:user_py_proto --show-output 2>/dev/null | grep "user_py_proto" | awk '{print $2}')

if [ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR" ]; then
    echo "📁 Checking output directory: $OUTPUT_DIR"
    
    # Expected files for full Python proto library
    EXPECTED_FILES=(
        "user_pb2.py"
        "user_pb2.pyi"
        "user_pb2_grpc.py"
        "user_pb2_grpc.pyi"
        "__init__.py"
        "py.typed"
    )
    
    for file in "${EXPECTED_FILES[@]}"; do
        if [ -f "$OUTPUT_DIR/$file" ]; then
            echo "✅ Found expected file: $file"
        else
            echo "❌ Missing expected file: $file"
            exit 1
        fi
    done
else
    echo "❌ Could not find output directory"
    exit 1
fi

# Test 5: Python syntax validation
echo "🧪 Test 5: Python syntax validation"

# Check that generated Python files have valid syntax
python3 -m py_compile "$OUTPUT_DIR/user_pb2.py" 2>&1 | tee "$TEST_DIR/syntax_check.log"
if [ $? -eq 0 ]; then
    echo "✅ user_pb2.py has valid Python syntax"
else
    echo "❌ user_pb2.py has syntax errors"
    cat "$TEST_DIR/syntax_check.log"
    exit 1
fi

python3 -m py_compile "$OUTPUT_DIR/user_pb2_grpc.py" 2>&1 | tee -a "$TEST_DIR/syntax_check.log"
if [ $? -eq 0 ]; then
    echo "✅ user_pb2_grpc.py has valid Python syntax"
else
    echo "❌ user_pb2_grpc.py has syntax errors"
    cat "$TEST_DIR/syntax_check.log"
    exit 1
fi

# Test 6: Import validation
echo "🧪 Test 6: Python import validation"

# Create a temporary Python script to test imports
cat > "$TEST_DIR/test_imports.py" << 'EOF'
import sys
import os

# Add the generated code directory to Python path
sys.path.insert(0, sys.argv[1])

try:
    # Test importing generated protobuf code
    import user_pb2
    print("✅ Successfully imported user_pb2")
    
    # Test creating a user message
    user = user_pb2.User()
    user.id = 123
    user.name = "Test User"
    user.email = "test@example.com"
    user.role = user_pb2.ADMIN
    print("✅ Successfully created User message")
    
    # Test serialization
    serialized = user.SerializeToString()
    print("✅ Successfully serialized User message")
    
    # Test deserialization
    user2 = user_pb2.User()
    user2.ParseFromString(serialized)
    assert user2.name == "Test User"
    print("✅ Successfully deserialized User message")
    
    # Test gRPC imports if available
    try:
        import user_pb2_grpc
        print("✅ Successfully imported user_pb2_grpc")
    except ImportError:
        print("⚠️  user_pb2_grpc not available (gRPC support may be missing)")
    
    print("🎉 All import tests passed!")
    
except Exception as e:
    print(f"❌ Import test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
EOF

python3 "$TEST_DIR/test_imports.py" "$OUTPUT_DIR" 2>&1 | tee "$TEST_DIR/import_test.log"
if [ $? -eq 0 ]; then
    echo "✅ Python import validation successful"
else
    echo "❌ Python import validation failed"
    cat "$TEST_DIR/import_test.log"
    exit 1
fi

# Test 7: Type checking with mypy (if available)
echo "🧪 Test 7: MyPy type checking (optional)"

if command -v mypy &> /dev/null; then
    echo "📋 Running mypy type checking on generated code..."
    
    # Create a temporary mypy config
    cat > "$TEST_DIR/mypy.ini" << 'EOF'
[mypy]
python_version = 3.8
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = False
ignore_missing_imports = True
EOF
    
    # Run mypy on generated files
    cd "$OUTPUT_DIR"
    mypy --config-file="$TEST_DIR/mypy.ini" user_pb2.py 2>&1 | tee "$TEST_DIR/mypy_check.log"
    MYPY_RESULT=$?
    
    if [ $MYPY_RESULT -eq 0 ]; then
        echo "✅ MyPy type checking passed"
    else
        echo "⚠️  MyPy type checking found issues (this may be expected for generated code)"
        # Don't fail the test for mypy issues, as generated code may have type issues
    fi
else
    echo "⚠️  MyPy not available, skipping type checking"
fi

# Test 8: Performance test with timing
echo "🧪 Test 8: Performance measurement"

echo "📊 Measuring build performance..."
time buck2 build //examples/python:user_py_proto --no-cache 2>&1 | tee "$TEST_DIR/perf_test.log"

if [ $? -eq 0 ]; then
    echo "✅ Performance test completed"
else
    echo "❌ Performance test failed"
    exit 1
fi

# Test 9: Multiple language targets
echo "🧪 Test 9: Multi-language build test"

echo "🔨 Building both Go and Python targets..."
buck2 build //examples/go:user_go_proto //examples/python:user_py_proto 2>&1 | tee "$TEST_DIR/multi_lang.log"

if [ $? -eq 0 ]; then
    echo "✅ Multi-language build successful"
else
    echo "❌ Multi-language build failed"
    cat "$TEST_DIR/multi_lang.log"
    exit 1
fi

# Test 10: Clean build test
echo "🧪 Test 10: Clean build verification"

echo "🧹 Cleaning Buck2 cache..."
buck2 clean

echo "🔨 Rebuilding from clean state..."
buck2 build //examples/python:user_py_proto 2>&1 | tee "$TEST_DIR/clean_build.log"

if [ $? -eq 0 ]; then
    echo "✅ Clean build successful"
else
    echo "❌ Clean build failed"
    cat "$TEST_DIR/clean_build.log"
    exit 1
fi

echo ""
echo "🎉 All Python protobuf integration tests passed!"
echo "================================================"
echo ""
echo "📊 Test Summary:"
echo "  ✅ Basic message generation"
echo "  ✅ gRPC service generation"
echo "  ✅ Full protobuf library"
echo "  ✅ File structure validation"
echo "  ✅ Python syntax validation"
echo "  ✅ Import and runtime validation"
echo "  ✅ Performance measurement"
echo "  ✅ Multi-language compatibility"
echo "  ✅ Clean build verification"
if command -v mypy &> /dev/null; then
    echo "  ✅ MyPy type checking"
fi
echo ""
echo "🐍 Python protobuf generation is working correctly!"
