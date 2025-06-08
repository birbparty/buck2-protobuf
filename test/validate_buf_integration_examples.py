#!/usr/bin/env python3
"""
Validation script for buf integration examples.

This script validates that all buf integration examples are correctly structured
and contain the necessary files for demonstration purposes.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Set


class BufExampleValidator:
    """Validates buf integration examples structure and content."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.examples_dir = self.base_dir / "examples" / "buf-integration"
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def validate_all(self) -> bool:
        """Validate all buf integration examples."""
        print("🔍 Validating buf integration examples...")
        
        # Check main structure
        self.validate_main_structure()
        
        # Validate quickstart examples
        self.validate_quickstart_examples()
        
        # Validate ORAS registry examples
        self.validate_oras_examples()
        
        # Report results
        return self.report_results()
    
    def validate_main_structure(self):
        """Validate main directory structure."""
        print("📁 Validating main structure...")
        
        required_files = [
            "README.md",
            "quickstart/README.md",
            "oras-registry/README.md",
        ]
        
        for file_path in required_files:
            full_path = self.examples_dir / file_path
            if not full_path.exists():
                self.errors.append(f"Missing required file: {file_path}")
            else:
                print(f"  ✅ {file_path}")
    
    def validate_quickstart_examples(self):
        """Validate quickstart examples."""
        print("🚀 Validating quickstart examples...")
        
        # Basic lint example
        basic_lint_dir = self.examples_dir / "quickstart" / "basic-lint"
        required_files = [
            "README.md",
            "BUCK",
            "buf.yaml",
            "user_service.proto",
            "bad_example.proto",
        ]
        
        self.validate_example_directory(basic_lint_dir, "basic-lint", required_files)
        
        # Validate content patterns
        self.validate_proto_content(basic_lint_dir / "user_service.proto", "good")
        self.validate_proto_content(basic_lint_dir / "bad_example.proto", "bad")
        self.validate_buck_content(basic_lint_dir / "BUCK", "basic-lint")
        self.validate_buf_yaml_content(basic_lint_dir / "buf.yaml", "basic")
    
    def validate_oras_examples(self):
        """Validate ORAS registry examples."""
        print("🏗️  Validating ORAS registry examples...")
        
        # Private dependencies example
        private_deps_dir = self.examples_dir / "oras-registry" / "private-deps"
        required_files = [
            "BUCK",
            "buf.yaml", 
            "service.proto",
        ]
        
        self.validate_example_directory(private_deps_dir, "private-deps", required_files)
        
        # Validate ORAS-specific content
        self.validate_oras_proto_content(private_deps_dir / "service.proto")
        self.validate_oras_buck_content(private_deps_dir / "BUCK")
        self.validate_oras_buf_yaml_content(private_deps_dir / "buf.yaml")
    
    def validate_example_directory(self, dir_path: Path, name: str, required_files: List[str]):
        """Validate an example directory has required files."""
        if not dir_path.exists():
            self.errors.append(f"Example directory missing: {name}")
            return
            
        for file_name in required_files:
            file_path = dir_path / file_name
            if not file_path.exists():
                self.errors.append(f"Missing file in {name}: {file_name}")
            else:
                print(f"  ✅ {name}/{file_name}")
    
    def validate_proto_content(self, file_path: Path, expected_type: str):
        """Validate protobuf file content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for basic proto structure
        if "syntax = \"proto3\";" not in content:
            self.errors.append(f"{file_path.name}: Missing proto3 syntax declaration")
        
        if "package " not in content:
            self.errors.append(f"{file_path.name}: Missing package declaration")
        
        if expected_type == "good":
            # Check for proper documentation
            if "service " in content and "//" not in content:
                self.warnings.append(f"{file_path.name}: Should have service documentation")
                
            # Check for proper naming patterns
            if "service " in content:
                lines = content.split('\n')
                for line in lines:
                    if line.strip().startswith('service '):
                        service_name = line.split()[1].rstrip(' {')
                        if not service_name.endswith('Service'):
                            self.warnings.append(f"{file_path.name}: Service should end with 'Service'")
        
        elif expected_type == "bad":
            # Should contain intentional violations
            if "ISSUE:" not in content:
                self.warnings.append(f"{file_path.name}: Should contain issue markers for demonstration")
    
    def validate_oras_proto_content(self, file_path: Path):
        """Validate ORAS-specific protobuf content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for ORAS imports
        if "oras.birb.homes" not in content:
            self.errors.append(f"{file_path.name}: Should import from oras.birb.homes registry")
        
        # Check for BSR imports too (hybrid approach)
        if "buf.build/googleapis" not in content:
            self.warnings.append(f"{file_path.name}: Should demonstrate hybrid BSR+ORAS usage")
    
    def validate_buck_content(self, file_path: Path, example_type: str):
        """Validate BUCK file content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for required rule loads
        if 'load("//rules:buf.bzl"' not in content:
            self.errors.append(f"{file_path.name}: Missing buf rules load")
        
        if 'load("//rules:proto.bzl"' not in content:
            self.errors.append(f"{file_path.name}: Missing proto rules load")
        
        # Check for basic rule usage
        if "buf_lint(" not in content:
            self.warnings.append(f"{file_path.name}: Should demonstrate buf_lint usage")
        
        if "proto_library(" not in content:
            self.errors.append(f"{file_path.name}: Should have proto_library targets")
    
    def validate_oras_buck_content(self, file_path: Path):
        """Validate ORAS-specific BUCK content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for ORAS dependencies
        if "oras_deps" not in content:
            self.errors.append(f"{file_path.name}: Should demonstrate oras_deps usage")
        
        # Check for BSR dependencies (hybrid approach)
        if "bsr_deps" not in content:
            self.warnings.append(f"{file_path.name}: Should demonstrate hybrid BSR+ORAS usage")
    
    def validate_buf_yaml_content(self, file_path: Path, config_type: str):
        """Validate buf.yaml configuration content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for basic structure
        if "version: v1" not in content:
            self.errors.append(f"{file_path.name}: Missing version declaration")
        
        if "lint:" not in content:
            self.warnings.append(f"{file_path.name}: Should have lint configuration")
        
        if config_type == "basic":
            # Check for basic lint rules
            if "DEFAULT" not in content:
                self.warnings.append(f"{file_path.name}: Should use DEFAULT lint rules")
    
    def validate_oras_buf_yaml_content(self, file_path: Path):
        """Validate ORAS-specific buf.yaml content."""
        if not file_path.exists():
            return
            
        content = file_path.read_text()
        
        # Check for ORAS dependencies
        if "oras.birb.homes" not in content:
            self.errors.append(f"{file_path.name}: Should have oras.birb.homes dependencies")
        
        # Check for BSR dependencies (hybrid approach)
        if "buf.build/" not in content:
            self.warnings.append(f"{file_path.name}: Should demonstrate hybrid BSR+ORAS usage")
    
    def report_results(self) -> bool:
        """Report validation results."""
        print("\n📊 Validation Results:")
        
        if not self.errors and not self.warnings:
            print("🎉 All buf integration examples are valid!")
            return True
        
        if self.errors:
            print(f"\n❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        success = len(self.errors) == 0
        if success:
            print("\n✅ Validation passed with warnings")
        else:
            print("\n❌ Validation failed")
        
        return success


def main():
    """Main validation function."""
    validator = BufExampleValidator()
    success = validator.validate_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
