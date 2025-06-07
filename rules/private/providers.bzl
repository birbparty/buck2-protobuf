"""Provider definitions for protobuf Buck2 integration.

This module defines the providers used to pass information between protobuf
rules. Implementation will be completed in Task 002.
"""

# ProtoInfo provider - will be fully implemented in Task 002
ProtoInfo = provider(fields = [
    "descriptor_set",        # Compiled protobuf descriptor set
    "proto_files",          # Source .proto files
    "import_paths",         # Import paths for this library
    "transitive_descriptor_sets",  # All descriptor sets from deps
    "transitive_proto_files",      # All proto files from deps
    "transitive_import_paths",     # All import paths from deps
    "go_package",           # Go package path (if specified)
    "python_package",       # Python package path (if specified)
    "java_package",         # Java package path (if specified)
    "lint_report",          # Lint validation report
    "breaking_report",      # Breaking change report
])

# LanguageProtoInfo provider - will be implemented across language tasks
LanguageProtoInfo = provider(fields = [
    "language",             # Target language ("go", "python", etc.)
    "generated_files",      # Generated source files
    "package_name",         # Language-specific package name
    "dependencies",         # Language-specific dependencies
    "compiler_flags",       # Language-specific compiler flags
])
