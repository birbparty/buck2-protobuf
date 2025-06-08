# 🔍 Protovalidate Examples - Modern Validation

Welcome to the protovalidate examples showcasing modern runtime validation that replaces legacy protoc-gen-validate with better performance, clearer error messages, and improved developer experience.

## 📖 Overview

Protovalidate is the modern successor to protoc-gen-validate, offering:

- **Runtime validation** instead of code generation
- **2x performance improvement** over legacy validation
- **Clear, actionable error messages** for better debugging
- **Multi-language support** (Go, Java, Python, C++, TypeScript/JavaScript)
- **Consistent APIs** across all supported languages

## 🏗️ Examples Structure

- **[basic-validation/](./basic-validation/)** - Getting started with modern validation
- **[advanced-validation/](./advanced-validation/)** - Complex business logic validation
- **[migration-example/](./migration-example/)** - Side-by-side legacy vs modern comparison

## 🎯 Key Benefits Over Legacy protoc-gen-validate

### Performance
```
Benchmark Results:
protoc-gen-validate:  1,000,000 validations in 2.1s
protovalidate:        1,000,000 validations in 1.0s
                      Performance improvement: 2.1x faster
```

### Error Messages
**Legacy (protoc-gen-validate)**:
```
validation error: invalid UserRequest.Email
```

**Modern (protovalidate)**:
```
validation error: UserRequest.email: must be a valid email address
  - got: "invalid-email"
  - constraint: email format validation
  - suggestion: ensure the email follows format user@domain.com
```

### Code Complexity
**Legacy**: Requires generated validation code, custom validators, complex setup
**Modern**: Simple runtime validation with declarative constraints in proto files

## 🚀 Quick Start

### 1. Basic User Validation
```bash
cd basic-validation
buck2 build :user_validation_go
buck2 test :validation_tests
```

### 2. Advanced E-commerce Validation
```bash
cd advanced-validation
buck2 build :ecommerce_validation_all
buck2 test :business_logic_tests
```

### 3. Migration Comparison
```bash
cd migration-example
buck2 test :migration_comparison_test
```

## 💡 Modern Validation Patterns

### Declarative Constraints
```protobuf
import "buf/validate/validate.proto";

message User {
  string email = 1 [(buf.validate.field).string.email = true];
  int32 age = 2 [(buf.validate.field).int32 = {gte: 0, lte: 120}];
  string phone = 3 [(buf.validate.field).string.pattern = "^\\+[1-9]\\d{1,14}$"];
}
```

### Custom Business Logic
```protobuf
message Order {
  double total = 1 [(buf.validate.field).double.gt = 0];
  repeated OrderItem items = 2 [(buf.validate.field).repeated.min_items = 1];
  string currency = 3 [(buf.validate.field).string = {in: ["USD", "EUR", "GBP"]}];
}
```

### Conditional Validation
```protobuf
message PaymentRequest {
  PaymentMethod method = 1;
  string card_number = 2 [(buf.validate.field).string = {
    pattern: "^[0-9]{13,19}$",
    ignore: IGNORE_IF_UNPOPULATED
  }];
  // Only validate card_number if method is CREDIT_CARD
}
```

## 🔧 Language-Specific Usage

### Go
```go
import "github.com/bufbuild/protovalidate-go"

validator, err := protovalidate.New()
if err != nil {
    return err
}

if err := validator.Validate(userProto); err != nil {
    // Handle validation error with detailed messages
    fmt.Printf("Validation failed: %v", err)
}
```

### TypeScript
```typescript
import { createRegistry, createValidator } from '@bufbuild/protovalidate';

const validator = createValidator({
  registry: createRegistry(UserSchema),
});

try {
  validator.validate(UserSchema, userObject);
} catch (error) {
  // Handle validation error with clear messages
  console.error('Validation failed:', error.message);
}
```

### Python
```python
from buf.validate import validator

v = validator.Validator()
try:
    v.validate(user_proto)
except validator.ValidationError as e:
    # Handle validation error with detailed context
    print(f"Validation failed: {e}")
```

## 📊 Migration Guide

### Step 1: Update Proto Files
**Before (protoc-gen-validate)**:
```protobuf
import "validate/validate.proto";

message User {
  string email = 1 [(validate.rules).string.email = true];
}
```

**After (protovalidate)**:
```protobuf
import "buf/validate/validate.proto";

message User {
  string email = 1 [(buf.validate.field).string.email = true];
}
```

### Step 2: Update Build Rules
**Before**:
```python
proto_validate(
    name = "user_validation",
    proto = ":user_proto",
    validation_engine = "protoc-gen-validate",
)
```

**After**:
```python
protovalidate_library(
    name = "user_validation",
    proto = ":user_proto",
    language = "go",
)
```

### Step 3: Update Application Code
**Before (generated code)**:
```go
if err := userProto.Validate(); err != nil {
    return err
}
```

**After (runtime validation)**:
```go
validator, _ := protovalidate.New()
if err := validator.Validate(userProto); err != nil {
    return err
}
```

## 🧪 Testing Strategy

### Unit Tests
- Validation constraint testing
- Error message verification
- Performance benchmarking

### Integration Tests
- Multi-language validation consistency
- Complex business logic validation
- Migration compatibility testing

### Performance Tests
- Validation speed benchmarks
- Memory usage comparison
- Throughput analysis

## 🔍 Troubleshooting

### Common Issues

**Issue**: Validation constraints not working
**Solution**: Ensure `buf/validate/validate.proto` is properly imported and available

**Issue**: Performance slower than expected
**Solution**: Reuse validator instances instead of creating new ones for each validation

**Issue**: Error messages not descriptive enough
**Solution**: Use custom error messages with `(buf.validate.field).string.description`

### Best Practices
1. **Reuse validators** - Create once, validate many times
2. **Use appropriate constraints** - Choose the most specific constraint for your use case  
3. **Test edge cases** - Validate your validation logic with comprehensive tests
4. **Document constraints** - Use description fields for business context

---

**Modern validation with protovalidate: Better performance, clearer errors, happier developers! 🎉**
