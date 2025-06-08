"""Implementation of protovalidate validation functionality.

This module provides the core implementation for protovalidate-based validation
using runtime validation libraries for Go, Python, and TypeScript.
"""

load("//rules/private:providers.bzl", "ProtoInfo", "ProtovalidateInfo", "ValidationInfo")
load("//rules/private:utils.bzl", "merge_proto_infos")

def _get_protovalidate_runtime(ctx, language, version="latest"):
    """Get protovalidate runtime dependencies for the specified language."""
    
    # Import ORAS plugin distributor for runtime dependencies
    tools_dir = ctx.label.package + "/../../tools"
    
    runtime_configs = {
        "go": {
            "module_path": "buf.build/go/protovalidate",
            "version": version if version != "latest" else "0.6.3",
            "import_path": "buf.build/go/protovalidate",
        },
        "python": {
            "package": "protovalidate",
            "version": version if version != "latest" else "0.7.1",
            "import_name": "protovalidate",
        },
        "typescript": {
            "package": "@buf/protovalidate",
            "version": version if version != "latest" else "0.6.1",
            "import_name": "@buf/protovalidate",
        },
    }
    
    if language not in runtime_configs:
        fail(f"Unsupported language for protovalidate: {language}")
    
    return runtime_configs[language]

def _get_buf_validate_schema(ctx):
    """Get the buf/validate/validate.proto schema file."""
    
    # Create a script to download buf/validate schema via ORAS
    download_script = ctx.actions.declare_output("download_buf_validate.py")
    
    script_content = f"""#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '{ctx.label.package}/../../tools')

from oras_plugins import PluginOrasDistributor

def main():
    distributor = PluginOrasDistributor(verbose=True)
    
    try:
        # Get buf validate schema
        schema_path = distributor.get_plugin("buf-validate-proto", "1.0.4", "universal")
        
        # Copy schema files to output directory
        import shutil
        import tarfile
        from pathlib import Path
        
        output_dir = Path(sys.argv[1])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract schema if it's an archive
        if schema_path.endswith(('.tar', '.gz', '.tgz')):
            with tarfile.open(schema_path, 'r:*') as tar:
                tar.extractall(output_dir)
        else:
            # Direct file copy
            shutil.copy2(schema_path, output_dir / "validate.proto")
        
        print(f"Schema extracted to {{output_dir}}")
        
    except Exception as e:
        print(f"Failed to get buf validate schema: {{e}}", file=sys.stderr)
        # Fallback: create minimal schema
        schema_content = '''syntax = "proto3";
package buf.validate;

// Minimal buf.validate schema for compatibility
message FieldConstraints {{
  // String validation
  StringRules string = 1;
  // Numeric validation  
  Int32Rules int32 = 2;
  Int64Rules int64 = 3;
  // Boolean validation
  BoolRules bool = 4;
}}

message StringRules {{
  optional string pattern = 1;
  optional uint64 min_len = 2;
  optional uint64 max_len = 3;
}}

message Int32Rules {{
  optional int32 gte = 1;
  optional int32 lte = 2;
}}

message Int64Rules {{
  optional int64 gte = 1;
  optional int64 lte = 2;
}}

message BoolRules {{
  optional bool const = 1;
}}

extend google.protobuf.FieldOptions {{
  FieldConstraints field = 1159;
}}
'''
        with open(output_dir / "validate.proto", 'w') as f:
            f.write(schema_content)

if __name__ == "__main__":
    main()
"""
    
    ctx.actions.write(download_script, script_content, is_executable=True)
    
    # Create output directory for schema
    schema_dir = ctx.actions.declare_output("buf_validate_schema", dir=True)
    
    ctx.actions.run(
        inputs = [download_script],
        outputs = [schema_dir],
        arguments = [schema_dir.as_output()],
        executable = download_script,
        env = {
            "PYTHONPATH": f"{ctx.label.package}/../../tools",
        },
    )
    
    return schema_dir

def _generate_go_validation(ctx, proto_info, runtime_config, schema_dir):
    """Generate Go validation code using protovalidate."""
    
    output_file = ctx.actions.declare_output(f"{ctx.label.name}_validation.go")
    
    # Create Go validation code generator
    generator_script = ctx.actions.write(
        f"{ctx.label.name}_generate_go.py",
        content = f"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def generate_go_validation():
    output_file = sys.argv[1]
    proto_files = sys.argv[2:]
    
    # Generate Go validation wrapper code
    go_code = '''package validation

import (
    "context"
    "fmt"
    
    "buf.build/go/protovalidate"
    "google.golang.org/protobuf/proto"
)

// Validator wraps protovalidate.Validator for consistent API
type Validator struct {{
    validator *protovalidate.Validator
}}

// NewValidator creates a new protovalidate validator
func NewValidator() (*Validator, error) {{
    v, err := protovalidate.New()
    if err != nil {{
        return nil, fmt.Errorf("failed to create protovalidate validator: %w", err)
    }}
    
    return &Validator{{validator: v}}, nil
}}

// Validate validates a protobuf message using protovalidate constraints
func (v *Validator) Validate(msg proto.Message) error {{
    return v.validator.Validate(msg)
}}

// ValidateWithContext validates with context support
func (v *Validator) ValidateWithContext(ctx context.Context, msg proto.Message) error {{
    // protovalidate doesn't directly support context, but we can add timeout handling
    done := make(chan error, 1)
    go func() {{
        done <- v.validator.Validate(msg)
    }}()
    
    select {{
    case err := <-done:
        return err
    case <-ctx.Done():
        return ctx.Err()
    }}
}}
'''
    
    with open(output_file, 'w') as f:
        f.write(go_code)
    
    print(f"Generated Go validation code: {{output_file}}")

if __name__ == "__main__":
    generate_go_validation()
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [generator_script, schema_dir] + proto_info.proto_files,
        outputs = [output_file],
        arguments = [output_file.as_output()] + [f.as_output() for f in proto_info.proto_files],
        executable = generator_script,
    )
    
    return output_file

def _generate_python_validation(ctx, proto_info, runtime_config, schema_dir):
    """Generate Python validation code using protovalidate."""
    
    output_file = ctx.actions.declare_output(f"{ctx.label.name}_validation.py")
    
    # Create Python validation code generator
    generator_script = ctx.actions.write(
        f"{ctx.label.name}_generate_python.py",
        content = f"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def generate_python_validation():
    output_file = sys.argv[1]
    proto_files = sys.argv[2:]
    
    # Generate Python validation wrapper code
    python_code = '''"""Generated protovalidate validation wrapper."""

import protovalidate
from typing import Any, Optional
from google.protobuf.message import Message


class Validator:
    """Wrapper around protovalidate.Validator for consistent API."""
    
    def __init__(self):
        """Initialize the protovalidate validator."""
        self._validator = protovalidate.Validator()
    
    def validate(self, message: Message) -> None:
        """
        Validate a protobuf message using protovalidate constraints.
        
        Args:
            message: Protobuf message to validate
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            self._validator.validate(message)
        except Exception as e:
            raise ValidationError(f"Validation failed: {{e}}") from e
    
    def validate_with_options(self, message: Message, **kwargs) -> None:
        """
        Validate with additional options.
        
        Args:
            message: Protobuf message to validate
            **kwargs: Additional validation options
        """
        # protovalidate-python doesn't support additional options yet
        # but we provide the interface for future compatibility
        return self.validate(message)


class ValidationError(Exception):
    """Raised when protovalidate validation fails."""
    pass


# Convenience function for direct validation
def validate_message(message: Message) -> None:
    """
    Validate a message using the default validator.
    
    Args:
        message: Protobuf message to validate
        
    Raises:
        ValidationError: If validation fails
    """
    validator = Validator()
    validator.validate(message)
'''
    
    with open(output_file, 'w') as f:
        f.write(python_code)
    
    print(f"Generated Python validation code: {{output_file}}")

if __name__ == "__main__":
    generate_python_validation()
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [generator_script, schema_dir] + proto_info.proto_files,
        outputs = [output_file],
        arguments = [output_file.as_output()] + [f.as_output() for f in proto_info.proto_files],
        executable = generator_script,
    )
    
    return output_file

def _generate_typescript_validation(ctx, proto_info, runtime_config, schema_dir):
    """Generate TypeScript validation code using protovalidate."""
    
    output_file = ctx.actions.declare_output(f"{ctx.label.name}_validation.ts")
    
    # Create TypeScript validation code generator
    generator_script = ctx.actions.write(
        f"{ctx.label.name}_generate_typescript.py",
        content = f"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

def generate_typescript_validation():
    output_file = sys.argv[1]
    proto_files = sys.argv[2:]
    
    # Generate TypeScript validation wrapper code
    typescript_code = '''/**
 * Generated protovalidate validation wrapper for TypeScript.
 */

import {{ Validator as ProtovalidateValidator }} from '@buf/protovalidate';

/**
 * Validation error thrown when protovalidate validation fails.
 */
export class ValidationError extends Error {{
    constructor(message: string, public readonly cause?: Error) {{
        super(message);
        this.name = 'ValidationError';
    }}
}}

/**
 * Wrapper around protovalidate Validator for consistent API.
 */
export class Validator {{
    private validator: ProtovalidateValidator;
    
    constructor() {{
        this.validator = new ProtovalidateValidator();
    }}
    
    /**
     * Validate a protobuf message using protovalidate constraints.
     * 
     * @param message - Protobuf message to validate
     * @throws ValidationError if validation fails
     */
    validate(message: any): void {{
        try {{
            this.validator.validate(message);
        }} catch (error) {{
            throw new ValidationError(
                `Validation failed: ${{error instanceof Error ? error.message : String(error)}}`,
                error instanceof Error ? error : undefined
            );
        }}
    }}
    
    /**
     * Async validation wrapper for consistency with other language implementations.
     * 
     * @param message - Protobuf message to validate
     * @returns Promise that resolves if validation passes
     */
    async validateAsync(message: any): Promise<void> {{
        return Promise.resolve(this.validate(message));
    }}
    
    /**
     * Validate with additional options.
     * 
     * @param message - Protobuf message to validate
     * @param options - Additional validation options (future compatibility)
     */
    validateWithOptions(message: any, options?: Record<string, any>): void {{
        // protovalidate-js doesn't support additional options yet
        // but we provide the interface for future compatibility
        return this.validate(message);
    }}
}}

/**
 * Convenience function for direct validation.
 * 
 * @param message - Protobuf message to validate
 * @throws ValidationError if validation fails
 */
export function validateMessage(message: any): void {{
    const validator = new Validator();
    validator.validate(message);
}}

/**
 * Async convenience function for direct validation.
 * 
 * @param message - Protobuf message to validate
 * @returns Promise that resolves if validation passes
 */
export async function validateMessageAsync(message: any): Promise<void> {{
    const validator = new Validator();
    return validator.validateAsync(message);
}}
'''
    
    with open(output_file, 'w') as f:
        f.write(typescript_code)
    
    print(f"Generated TypeScript validation code: {{output_file}}")

if __name__ == "__main__":
    generate_typescript_validation()
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [generator_script, schema_dir] + proto_info.proto_files,
        outputs = [output_file],
        arguments = [output_file.as_output()] + [f.as_output() for f in proto_info.proto_files],
        executable = generator_script,
    )
    
    return output_file

def _maybe_use_bsr_cache(ctx, validation_files):
    """Optionally use BSR team caching for validation artifacts."""
    
    if not ctx.attr.bsr_cache:
        return validation_files
    
    # Create BSR caching integration
    cache_script = ctx.actions.write(
        f"{ctx.label.name}_bsr_cache.py",
        content = f"""#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, '{ctx.label.package}/../../tools')

from bsr_team_oras_cache import BSRTeamOrasCache

def main():
    cache = BSRTeamOrasCache(verbose=True)
    
    input_files = sys.argv[1:-1]
    output_dir = sys.argv[-1]
    
    try:
        # Use BSR team caching for validation artifacts
        cached_files = cache.cache_validation_artifacts(input_files)
        
        # Copy cached files to output
        import shutil
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, cached_file in enumerate(cached_files):
            output_file = output_path / f"cached_validation_{{i}}"
            shutil.copy2(cached_file, output_file)
        
        print(f"BSR cached {{len(cached_files)}} validation artifacts")
        
    except Exception as e:
        print(f"BSR caching failed, using original files: {{e}}", file=sys.stderr)
        # Fallback: copy original files
        import shutil
        from pathlib import Path
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, input_file in enumerate(input_files):
            output_file = output_path / f"validation_{{i}}"
            shutil.copy2(input_file, output_file)

if __name__ == "__main__":
    main()
""",
        is_executable = True,
    )
    
    cached_dir = ctx.actions.declare_output(f"{ctx.label.name}_cached", dir=True)
    
    ctx.actions.run(
        inputs = [cache_script] + validation_files,
        outputs = [cached_dir],
        arguments = [f.as_output() for f in validation_files] + [cached_dir.as_output()],
        executable = cache_script,
        env = {
            "PYTHONPATH": f"{ctx.label.package}/../../tools",
        },
    )
    
    return [cached_dir]

def protovalidate_library_impl(ctx):
    """Implementation of protovalidate_library rule."""
    
    # Get proto information
    proto_info = ctx.attr.proto[ProtoInfo]
    
    # Get buf validate schema
    schema_dir = _get_buf_validate_schema(ctx)
    
    # Get runtime configuration
    runtime_config = _get_protovalidate_runtime(ctx, ctx.attr.language)
    
    # Generate language-specific validation code
    if ctx.attr.language == "go":
        validation_file = _generate_go_validation(ctx, proto_info, runtime_config, schema_dir)
    elif ctx.attr.language == "python":
        validation_file = _generate_python_validation(ctx, proto_info, runtime_config, schema_dir)
    elif ctx.attr.language == "typescript":
        validation_file = _generate_typescript_validation(ctx, proto_info, runtime_config, schema_dir)
    else:
        fail(f"Unsupported language: {ctx.attr.language}")
    
    validation_files = [validation_file]
    
    # Apply BSR caching if requested
    if ctx.attr.bsr_cache:
        validation_files = _maybe_use_bsr_cache(ctx, validation_files)
    
    # Create validation metadata
    validation_metadata = ctx.actions.declare_output(f"{ctx.label.name}_metadata.json")
    
    metadata_script = ctx.actions.write(
        f"{ctx.label.name}_metadata.py",
        content = f"""#!/usr/bin/env python3
import json
import sys

metadata = {{
    "rule_type": "protovalidate_library",
    "language": "{ctx.attr.language}",
    "runtime_config": {runtime_config},
    "proto_files": [f for f in sys.argv[2:]],
    "validation_engine": "protovalidate",
    "bsr_cache_enabled": {ctx.attr.bsr_cache},
    "generated_files": [sys.argv[1]],
}}

with open(sys.argv[1], 'w') as f:
    json.dump(metadata, f, indent=2)
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [metadata_script] + proto_info.proto_files,
        outputs = [validation_metadata],
        arguments = [
            validation_metadata.as_output()
        ] + [f.as_output() for f in proto_info.proto_files],
        executable = metadata_script,
    )
    
    # Create providers
    protovalidate_info = ProtovalidateInfo(
        language = ctx.attr.language,
        runtime_config = runtime_config,
        validation_files = validation_files,
        schema_dir = schema_dir,
    )
    
    validation_info = ValidationInfo(
        passed = True,  # Always passes during generation
        validation_engine = "protovalidate",
        language = ctx.attr.language,
        metadata = validation_metadata,
    )
    
    return [
        DefaultInfo(files = depset(validation_files + [validation_metadata])),
        protovalidate_info,
        validation_info,
    ]

def protovalidate_runtime_impl(ctx):
    """Implementation of protovalidate_runtime rule."""
    
    # Get runtime configuration
    runtime_config = _get_protovalidate_runtime(ctx, ctx.attr.language, ctx.attr.version)
    
    # Create runtime dependency file
    runtime_deps_file = ctx.actions.declare_output(f"{ctx.label.name}_runtime_deps.json")
    
    deps_script = ctx.actions.write(
        f"{ctx.label.name}_deps.py",
        content = f"""#!/usr/bin/env python3
import json
import sys

runtime_deps = {{
    "language": "{ctx.attr.language}",
    "version": "{ctx.attr.version}",
    "runtime_config": {runtime_config},
    "additional_deps": [],  # Would be populated from ctx.attr.additional_deps
}}

with open(sys.argv[1], 'w') as f:
    json.dump(runtime_deps, f, indent=2)
""",
        is_executable = True,
    )
    
    ctx.actions.run(
        inputs = [deps_script],
        outputs = [runtime_deps_file],
        arguments = [runtime_deps_file.as_output()],
        executable = deps_script,
    )
    
    # Create providers
    protovalidate_info = ProtovalidateInfo(
        language = ctx.attr.language,
        runtime_config = runtime_config,
        validation_files = [],
        schema_dir = None,
    )
    
    return [
        DefaultInfo(files = depset([runtime_deps_file])),
        protovalidate_info,
    ]
