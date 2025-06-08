# Protovalidate Integration Test Report

## Summary
- **Total Tests**: 5
- **Passed**: 2
- **Failed**: 3
- **Success Rate**: 40.0%

## Test Results

### Plugin Availability
- ✗ **buf-validate-proto** v1.0.4
  - Error: Both ORAS and HTTP failed for plugin buf-validate-proto 1.0.4 universal: Unsupported plugin: buf-validate-proto. Available plugins: ['protoc-gen-go', 'protoc-gen-grpc-go', 'protoc-gen-grpc-python']
- ✗ **protovalidate-go** v0.6.3
  - Error: Both ORAS and HTTP failed for plugin protovalidate-go 0.6.3 universal: Unsupported plugin: protovalidate-go. Available plugins: ['protoc-gen-go', 'protoc-gen-grpc-go', 'protoc-gen-grpc-python']
- ✗ **protovalidate-python** v0.7.1
  - Error: 'binary_path'
- ✗ **protovalidate-js** v0.6.1
  - Error: 'binary_path'

### Runtime Libraries
- ✗ **go** runtime v0.6.3
- ✗ **python** runtime v0.7.1
- ✗ **typescript** runtime v0.6.1

### Performance Metrics
- **ORAS Hit Rate**: 0.0%
- **Cache Hit Rate**: 0.0%
- **Total Requests**: 10
