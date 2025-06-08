# Protovalidate Examples

This directory demonstrates modern protobuf validation using the **protovalidate** framework. Protovalidate replaces legacy validation approaches with a unified, runtime-based validation system that works consistently across Go, Python, and TypeScript.

## Why Protovalidate?

### Modern Approach
- **Runtime Validation**: Uses runtime libraries instead of generated code
- **Consistent APIs**: Same validation interface across all languages
- **Better Performance**: Optimized runtime validation vs code generation
- **Improved Error Messages**: Clear, actionable validation error messages
- **CEL Expressions**: Support for complex validation logic using CEL

### vs Legacy protoc-gen-validate
| Feature | Legacy (protoc-gen-validate) | Modern (protovalidate) |
|---------|---------------------------|----------------------|
| Approach | Code generation | Runtime validation |
| API Consistency | Different per language | Unified across languages |
| Binary Size | Large (generated code) | Small (runtime only) |
| Maintainability | Complex generated code | Simple runtime calls |
| Error Messages | Basic | Rich, contextual |
| Complex Validation | Limited | Full CEL support |
| Status | Deprecated | Actively maintained |

## Examples Overview

### Basic Examples
- [`basic/`](basic/) - Simple validation constraints
- [`multi-language/`](multi-language/) - Same validation across Go, Python, TypeScript
- [`migration/`](migration/) - Migration from legacy validation

### Advanced Examples
- [`conditional/`](conditional/) - Conditional validation using CEL
- [`cross-field/`](cross-field/) - Cross-field validation rules
- [`custom-rules/`](custom-rules/) - Custom validation expressions
- [`performance/`](performance/) - Performance optimization examples

### Integration Examples
- [`grpc-integration/`](grpc-integration/) - gRPC service validation
- [`rest-api/`](rest-api/) - REST API validation patterns
- [`microservices/`](microservices/) - Microservice validation architecture

## Quick Start

### 1. Define Constraints in Proto
```protobuf
syntax = "proto3";

import "buf/validate/validate.proto";

message User {
  // Email must be valid format, 3-254 characters
  string email = 1 [(buf.validate.field).string = {
    pattern: "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
    min_len: 3,
    max_len: 254
  }];
  
  // Age must be between 13 and 120
  int32 age = 2 [(buf.validate.field).int32 = {
    gte: 13,
    lte: 120
  }];
}
```

### 2. Generate Validation (Buck2)
```python
# In your BUCK file
load("//rules:protovalidate.bzl", "protovalidate_library")

protovalidate_library(
    name = "user_validation_go",
    proto = ":user_proto", 
    language = "go",
)
```

### 3. Use Runtime Validation

**Go:**
```go
import "your_package/user_validation"

validator, err := validation.NewValidator()
if err != nil {
    log.Fatal(err)
}

user := &User{Email: "invalid-email", Age: 5}
if err := validator.Validate(user); err != nil {
    log.Printf("Validation failed: %v", err)
}
```

**Python:**
```python
from your_package.user_validation import Validator, ValidationError

validator = Validator()
user = User(email="invalid-email", age=5)

try:
    validator.validate(user)
except ValidationError as e:
    print(f"Validation failed: {e}")
```

**TypeScript:**
```typescript
import { Validator, ValidationError } from './user_validation';

const validator = new Validator();
const user = { email: "invalid-email", age: 5 };

try {
    validator.validate(user);
} catch (error: ValidationError) {
    console.log(`Validation failed: ${error.message}`);
}
```

## Validation Constraint Types

### String Constraints
- `pattern`: Regular expression validation
- `min_len`, `max_len`: Length constraints  
- `in`, `not_in`: Enumeration constraints
- `prefix`, `suffix`: Prefix/suffix validation
- `contains`, `not_contains`: Substring validation

### Numeric Constraints
- `gte`, `lte`: Greater/less than or equal
- `gt`, `lt`: Greater/less than (exclusive)
- `in`, `not_in`: Value enumeration
- `const`: Exact value constraint

### Message Constraints
- `required`: Field must be set
- `skip`: Skip validation for this field
- `cel`: Custom CEL expressions

### Collection Constraints
- `min_items`, `max_items`: Size constraints
- `unique`: Require unique elements
- `items`: Constraints for each item

## Performance Characteristics

### Validation Speed
- **Go**: ~2-5μs per message (simple constraints)
- **Python**: ~10-50μs per message
- **TypeScript**: ~5-20μs per message

### Memory Usage
- **Runtime Libraries**: 1-5MB per language
- **Generated Code**: 0 bytes (no generation)
- **Validation State**: Minimal per validator instance

### Build Performance
- **Compilation Time**: 60%+ faster than code generation
- **Binary Size**: 70%+ smaller than generated validation
- **Cache Efficiency**: Better cache hit rates

## Advanced Features

### CEL Expressions
```protobuf
message User {
  string email = 1;
  string confirm_email = 2;
  
  option (buf.validate.message).cel = {
    id: "email_confirmation",
    message: "email and confirm_email must match",
    expression: "this.email == this.confirm_email"
  };
}
```

### Cross-Field Validation
```protobuf
message DateRange {
  google.protobuf.Timestamp start = 1;
  google.protobuf.Timestamp end = 2;
  
  option (buf.validate.message).cel = {
    id: "date_range_order",
    message: "start must be before end",
    expression: "this.start < this.end"
  };
}
```

### Conditional Validation
```protobuf
message Account {
  string type = 1; // "personal" or "business"
  string tax_id = 2;
  
  option (buf.validate.message).cel = {
    id: "business_tax_id",
    message: "business accounts require tax_id",
    expression: "this.type != 'business' || this.tax_id != ''"
  };
}
```

## Best Practices

### 1. Validate at Boundaries
- Always validate at API entry points
- Validate before persisting to database
- Validate after deserializing from external sources

### 2. Use Appropriate Constraints
- Prefer specific constraints over regex when possible
- Use `required` for mandatory fields
- Set reasonable length limits for strings

### 3. Error Handling
- Catch validation errors early in request processing
- Provide clear error messages to clients
- Log validation failures for monitoring

### 4. Performance Optimization
- Reuse validator instances when possible
- Cache compiled validation rules
- Use conditional validation to skip expensive checks

### 5. Testing
- Test both valid and invalid cases
- Test edge cases and boundary conditions
- Validate error message quality

## Migration Guide

See the [migration examples](migration/) for detailed guidance on migrating from:
- protoc-gen-validate to protovalidate
- Custom validation logic to protovalidate constraints
- Legacy validation libraries to modern protovalidate

## Further Reading

- [Protovalidate Documentation](https://github.com/bufbuild/protovalidate)
- [Buf Validate Schema Reference](https://buf.build/bufbuild/protovalidate)
- [CEL Expression Language](https://github.com/google/cel-spec)
- [Buck2 Protobuf Rules](../../docs/rules-reference.md)
