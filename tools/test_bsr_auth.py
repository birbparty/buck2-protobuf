#!/usr/bin/env python3
"""
Comprehensive test suite for BSR Authentication System.

This module tests all authentication methods, security features,
and integration patterns for the BSR authentication system.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import subprocess

# Import the BSR authentication components
try:
    from bsr_auth import (
        BSRAuthenticator, BSRCredentials, BSRCredentialManager,
        BSRAuthenticationError, ServiceAccountCredentials,
        KEYRING_AVAILABLE, CRYPTOGRAPHY_AVAILABLE
    )
except ImportError:
    # Handle direct execution
    import sys
    sys.path.append(str(Path(__file__).parent))
    from bsr_auth import (
        BSRAuthenticator, BSRCredentials, BSRCredentialManager,
        BSRAuthenticationError, ServiceAccountCredentials,
        KEYRING_AVAILABLE, CRYPTOGRAPHY_AVAILABLE
    )


class TestBSRCredentials(unittest.TestCase):
    """Test BSR credentials data structure."""
    
    def test_credential_creation(self):
        """Test creating BSR credentials."""
        creds = BSRCredentials(
            token="test_token_123456",
            username="testuser",
            registry="buf.build"
        )
        
        self.assertEqual(creds.token, "test_token_123456")
        self.assertEqual(creds.username, "testuser")
        self.assertEqual(creds.registry, "buf.build")
        self.assertIsNotNone(creds.created_at)
        self.assertFalse(creds.is_expired())
    
    def test_credential_validation(self):
        """Test credential validation."""
        # Valid token
        creds = BSRCredentials(token="valid_token_123456")
        self.assertEqual(creds.token, "valid_token_123456")
        
        # Invalid token (too short)
        with self.assertRaises(ValueError):
            BSRCredentials(token="short")
        
        # Empty token
        with self.assertRaises(ValueError):
            BSRCredentials(token="")
    
    def test_token_masking(self):
        """Test token masking for safe logging."""
        creds = BSRCredentials(token="abcdefghijklmnop")
        masked = creds.mask_token()
        self.assertEqual(masked, "abcd...mnop")
        
        # Short token
        short_creds = BSRCredentials(token="short_token")
        short_masked = short_creds.mask_token()
        self.assertEqual(short_masked, "shor...oken")
    
    def test_expiration(self):
        """Test credential expiration."""
        # Non-expired credentials
        creds = BSRCredentials(
            token="test_token_123456",
            expires_at=time.time() + 3600  # 1 hour from now
        )
        self.assertFalse(creds.is_expired())
        
        # Expired credentials
        expired_creds = BSRCredentials(
            token="test_token_123456",
            expires_at=time.time() - 3600  # 1 hour ago
        )
        self.assertTrue(expired_creds.is_expired())
    
    def test_serialization(self):
        """Test credential serialization and deserialization."""
        original_creds = BSRCredentials(
            token="test_token_123456",
            username="testuser",
            registry="buf.build/myorg",
            auth_method="environment"
        )
        
        # Serialize to dict
        creds_dict = original_creds.to_dict()
        self.assertIsInstance(creds_dict, dict)
        self.assertEqual(creds_dict['token'], "test_token_123456")
        
        # Deserialize from dict
        restored_creds = BSRCredentials.from_dict(creds_dict)
        self.assertEqual(restored_creds.token, original_creds.token)
        self.assertEqual(restored_creds.username, original_creds.username)
        self.assertEqual(restored_creds.registry, original_creds.registry)


class TestBSRCredentialManager(unittest.TestCase):
    """Test BSR credential storage manager."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.credential_manager = BSRCredentialManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_credential_storage_and_retrieval(self):
        """Test storing and retrieving credentials."""
        repository = "buf.build/testorg"
        creds = BSRCredentials(
            token="test_token_123456",
            username="testuser",
            registry=repository,
            auth_method="test"
        )
        
        # Store credentials
        self.credential_manager.store_credentials(repository, creds)
        
        # Retrieve credentials
        retrieved_creds = self.credential_manager.retrieve_credentials(repository)
        self.assertIsNotNone(retrieved_creds)
        self.assertEqual(retrieved_creds.token, creds.token)
        self.assertEqual(retrieved_creds.username, creds.username)
    
    def test_nonexistent_credentials(self):
        """Test retrieving non-existent credentials."""
        retrieved_creds = self.credential_manager.retrieve_credentials("nonexistent.repo")
        self.assertIsNone(retrieved_creds)
    
    def test_credential_deletion(self):
        """Test deleting stored credentials."""
        repository = "buf.build/testorg"
        creds = BSRCredentials(token="test_token_123456")
        
        # Store and verify
        self.credential_manager.store_credentials(repository, creds)
        self.assertIsNotNone(self.credential_manager.retrieve_credentials(repository))
        
        # Delete and verify
        deleted = self.credential_manager.delete_credentials(repository)
        self.assertTrue(deleted)
        self.assertIsNone(self.credential_manager.retrieve_credentials(repository))
    
    def test_list_repositories(self):
        """Test listing repositories with stored credentials."""
        repositories = ["buf.build/org1", "buf.build/org2", "buf.build/org3"]
        
        # Store credentials for multiple repositories
        for repo in repositories:
            creds = BSRCredentials(token=f"token_for_{repo.replace('/', '_')}")
            self.credential_manager.store_credentials(repo, creds)
        
        # List stored repositories
        stored_repos = self.credential_manager.list_stored_repositories()
        self.assertEqual(set(stored_repos), set(repositories))
    
    def test_clear_all_credentials(self):
        """Test clearing all stored credentials."""
        repositories = ["buf.build/org1", "buf.build/org2"]
        
        # Store credentials for multiple repositories
        for repo in repositories:
            creds = BSRCredentials(token=f"token_for_{repo.replace('/', '_')}")
            self.credential_manager.store_credentials(repo, creds)
        
        # Clear all and verify
        cleared = self.credential_manager.clear_all_credentials()
        self.assertEqual(cleared, len(repositories))
        
        # Verify all are gone
        for repo in repositories:
            self.assertIsNone(self.credential_manager.retrieve_credentials(repo))
    
    def test_expired_credential_cleanup(self):
        """Test that expired credentials are automatically cleaned up."""
        repository = "buf.build/testorg"
        
        # Create expired credentials
        expired_creds = BSRCredentials(
            token="expired_token",
            expires_at=time.time() - 3600  # 1 hour ago
        )
        
        # Store expired credentials
        self.credential_manager.store_credentials(repository, expired_creds)
        
        # Attempt to retrieve - should return None and clean up
        retrieved_creds = self.credential_manager.retrieve_credentials(repository)
        self.assertIsNone(retrieved_creds)


class TestBSRAuthenticator(unittest.TestCase):
    """Test BSR authenticator with all authentication methods."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.authenticator = BSRAuthenticator(
            cache_dir=self.temp_dir,
            verbose=True
        )
        
        # Mock subprocess for buf CLI validation
        self.subprocess_patcher = patch('bsr_auth.subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()
        
        # Default successful validation
        self.mock_subprocess.return_value.returncode = 0
        self.mock_subprocess.return_value.stderr = ""
    
    def tearDown(self):
        """Clean up test environment."""
        self.subprocess_patcher.stop()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_environment_authentication(self):
        """Test authentication using environment variables."""
        with patch.dict(os.environ, {'BUF_TOKEN': 'env_test_token_123456'}):
            creds = self.authenticator.authenticate(method="environment")
            
            self.assertEqual(creds.token, 'env_test_token_123456')
            self.assertEqual(creds.auth_method, 'environment')
    
    def test_netrc_authentication(self):
        """Test authentication using .netrc file."""
        # Create a mock .netrc file
        netrc_content = """
machine buf.build
login testuser
password netrc_test_token_123456

machine other.registry
login otheruser
password othertoken
"""
        
        netrc_path = self.temp_dir / '.netrc'
        netrc_path.write_text(netrc_content)
        
        with patch('bsr_auth.Path.home', return_value=self.temp_dir):
            creds = self.authenticator.authenticate(method="netrc")
            
            self.assertEqual(creds.token, 'netrc_test_token_123456')
            self.assertEqual(creds.username, 'testuser')
            self.assertEqual(creds.auth_method, 'netrc')
    
    def test_service_account_authentication(self):
        """Test authentication using service account file."""
        # Create mock service account file
        service_account_data = {
            "account_id": "test-service-account",
            "private_key": "service_account_private_key_123456",
            "registry": "buf.build"
        }
        
        sa_file = self.temp_dir / 'service_account.json'
        sa_file.write_text(json.dumps(service_account_data))
        
        creds = self.authenticator.authenticate(
            method="service_account",
            service_account_file=str(sa_file)
        )
        
        self.assertEqual(creds.username, 'test-service-account')
        self.assertEqual(creds.auth_method, 'service_account')
    
    def test_interactive_authentication(self):
        """Test interactive authentication."""
        with patch('bsr_auth.getpass.getpass', return_value='interactive_test_token_123456'):
            with patch('builtins.print'):  # Suppress print statements
                creds = self.authenticator.authenticate(method="interactive")
                
                self.assertEqual(creds.token, 'interactive_test_token_123456')
                self.assertEqual(creds.auth_method, 'interactive')
    
    def test_auto_detection_priority(self):
        """Test automatic authentication method detection priority."""
        # Set up multiple authentication methods
        with patch.dict(os.environ, {'BUF_TOKEN': 'env_token_123456'}):
            # Environment should take priority
            creds = self.authenticator.authenticate(method="auto")
            self.assertEqual(creds.auth_method, 'environment')
    
    def test_credential_caching(self):
        """Test credential caching functionality."""
        repository = "buf.build/testorg"
        
        # First authentication
        with patch.dict(os.environ, {'BUF_TOKEN': 'cached_test_token_123456'}):
            creds1 = self.authenticator.authenticate(repository=repository)
            self.assertEqual(creds1.auth_method, 'environment')
        
        # Second authentication should use cached credentials
        with patch.dict(os.environ, {}, clear=True):  # Clear environment
            creds2 = self.authenticator.authenticate(repository=repository)
            self.assertEqual(creds2.token, 'cached_test_token_123456')
    
    def test_authentication_failure(self):
        """Test authentication failure handling."""
        # Clear all environment variables and ensure no auth methods work
        with patch.dict(os.environ, {}, clear=True):
            with patch('bsr_auth.Path.home') as mock_home:
                mock_home.return_value = Path("/nonexistent")
                
                with self.assertRaises(BSRAuthenticationError):
                    self.authenticator.authenticate()
    
    def test_credential_validation_failure(self):
        """Test handling of credential validation failure."""
        # Mock validation failure
        self.mock_subprocess.return_value.returncode = 1
        self.mock_subprocess.return_value.stderr = "Authentication failed"
        
        with patch.dict(os.environ, {'BUF_TOKEN': 'invalid_token'}):
            with self.assertRaises(BSRAuthenticationError):
                self.authenticator.authenticate()
    
    def test_logout_functionality(self):
        """Test logout and credential clearing."""
        repository = "buf.build/testorg"
        
        # Authenticate and store credentials
        with patch.dict(os.environ, {'BUF_TOKEN': 'logout_test_token_123456'}):
            self.authenticator.authenticate(repository=repository)
        
        # Verify credentials are stored
        status = self.authenticator.get_authentication_status(repository)
        self.assertTrue(status['authenticated'])
        
        # Logout
        logout_success = self.authenticator.logout(repository)
        self.assertTrue(logout_success)
        
        # Verify credentials are cleared
        status_after = self.authenticator.get_authentication_status(repository)
        self.assertFalse(status_after['authenticated'])
    
    def test_authentication_status(self):
        """Test authentication status reporting."""
        repository = "buf.build/testorg"
        
        # Check unauthenticated status
        status = self.authenticator.get_authentication_status(repository)
        self.assertFalse(status['authenticated'])
        self.assertEqual(status['repository'], repository)
        
        # Authenticate
        with patch.dict(os.environ, {'BUF_TOKEN': 'status_test_token_123456'}):
            self.authenticator.authenticate(repository=repository)
        
        # Check authenticated status
        auth_status = self.authenticator.get_authentication_status(repository)
        self.assertTrue(auth_status['authenticated'])
        self.assertEqual(auth_status['auth_method'], 'environment')
        self.assertIn('status...oken', auth_status['token_preview'])  # Masked token
    
    def test_list_authenticated_repositories(self):
        """Test listing authenticated repositories."""
        repositories = ["buf.build/org1", "buf.build/org2"]
        
        # Authenticate for multiple repositories
        for i, repo in enumerate(repositories):
            with patch.dict(os.environ, {'BUF_TOKEN': f'list_test_token_{i}'}):
                self.authenticator.authenticate(repository=repo)
        
        # List authenticated repositories
        auth_repos = self.authenticator.list_authenticated_repositories()
        self.assertEqual(set(auth_repos), set(repositories))


class TestSecurityFeatures(unittest.TestCase):
    """Test security features of the authentication system."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.credential_manager = BSRCredentialManager(self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_file_permissions(self):
        """Test that credential files have restrictive permissions."""
        if os.name == 'nt':  # Skip on Windows
            self.skipTest("File permission test not applicable on Windows")
        
        repository = "buf.build/testorg"
        creds = BSRCredentials(token="permission_test_token_123456")
        
        # Store credentials
        self.credential_manager.store_credentials(repository, creds)
        
        # Check file permissions
        encrypted_file = self.credential_manager.encrypted_storage_path
        if encrypted_file.exists():
            file_stat = encrypted_file.stat()
            # Check that file is readable/writable only by owner
            self.assertEqual(file_stat.st_mode & 0o777, 0o600)
    
    def test_token_format_validation(self):
        """Test token format validation."""
        # Valid tokens
        valid_tokens = [
            "buf_1234567890abcdef",
            "BSR_abcdef1234567890",
            "bsr_valid_token_123",
            "YWJjZGVmZ2hpams=",  # base64
            "abcdefghijklmnop1234567890"
        ]
        
        for token in valid_tokens:
            try:
                creds = BSRCredentials(token=token)
                self.assertIsNotNone(creds)
            except ValueError:
                self.fail(f"Valid token {token} was rejected")
        
        # Invalid tokens
        invalid_tokens = [
            "short",
            "",
            "invalid@token#with$symbols",
        ]
        
        for token in invalid_tokens:
            with self.assertRaises(ValueError):
                BSRCredentials(token=token)
    
    @unittest.skipIf(not CRYPTOGRAPHY_AVAILABLE, "Cryptography library not available")
    def test_encryption_fallback(self):
        """Test encryption and fallback mechanisms."""
        repository = "buf.build/testorg"
        creds = BSRCredentials(token="encryption_test_token_123456")
        
        # Store credentials (should use encryption if available)
        self.credential_manager.store_credentials(repository, creds)
        
        # Verify credentials can be retrieved
        retrieved_creds = self.credential_manager.retrieve_credentials(repository)
        self.assertIsNotNone(retrieved_creds)
        self.assertEqual(retrieved_creds.token, creds.token)
        
        # Verify encrypted file exists
        self.assertTrue(self.credential_manager.encrypted_storage_path.exists())


class TestIntegrationPatterns(unittest.TestCase):
    """Test integration patterns and real-world scenarios."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.authenticator = BSRAuthenticator(cache_dir=self.temp_dir)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_ci_cd_service_account_pattern(self):
        """Test CI/CD service account authentication pattern."""
        # Simulate CI/CD environment
        service_account_data = {
            "account_id": "ci-cd-service-account",
            "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----",
            "registry": "buf.build"
        }
        
        sa_file = self.temp_dir / 'ci_service_account.json'
        sa_file.write_text(json.dumps(service_account_data))
        
        # Set CI environment variable
        with patch.dict(os.environ, {'BSR_SERVICE_ACCOUNT_KEY': str(sa_file)}):
            with patch('bsr_auth.subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                
                creds = self.authenticator.authenticate(method="service_account")
                
                self.assertEqual(creds.username, 'ci-cd-service-account')
                self.assertEqual(creds.auth_method, 'service_account')
    
    def test_team_collaboration_pattern(self):
        """Test team collaboration authentication pattern."""
        team_repositories = [
            "buf.build/myteam/service1",
            "buf.build/myteam/service2",
            "buf.build/myteam/shared"
        ]
        
        # Simulate team member authenticating for multiple repositories
        with patch.dict(os.environ, {'BUF_TOKEN': 'team_member_token_123456'}):
            with patch('bsr_auth.subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                
                for repo in team_repositories:
                    creds = self.authenticator.authenticate(repository=repo)
                    self.assertEqual(creds.auth_method, 'environment')
        
        # Verify all repositories are authenticated
        auth_repos = self.authenticator.list_authenticated_repositories()
        self.assertEqual(set(auth_repos), set(team_repositories))
    
    def test_multi_registry_support(self):
        """Test authentication for multiple registries."""
        registries = [
            "buf.build",
            "private-bsr.company.com",
            "oras.birb.homes"
        ]
        
        with patch('bsr_auth.subprocess.run') as mock_subprocess:
            mock_subprocess.return_value.returncode = 0
            
            for i, registry in enumerate(registries):
                with patch.dict(os.environ, {'BUF_TOKEN': f'registry_token_{i}'}):
                    creds = self.authenticator.authenticate(repository=registry)
                    self.assertEqual(creds.registry, registry)
    
    def test_authentication_error_handling(self):
        """Test comprehensive error handling."""
        # Test network timeout
        with patch('bsr_auth.subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = subprocess.TimeoutExpired("buf", 30)
            
            with patch.dict(os.environ, {'BUF_TOKEN': 'timeout_test_token'}):
                # Should not raise exception due to timeout - validation gracefully handles it
                creds = self.authenticator.authenticate()
                self.assertIsNotNone(creds)
        
        # Test buf CLI not found
        with patch('bsr_auth.subprocess.run') as mock_subprocess:
            mock_subprocess.side_effect = FileNotFoundError("buf command not found")
            
            with patch.dict(os.environ, {'BUF_TOKEN': 'no_buf_cli_token'}):
                # Should not raise exception - assumes valid when buf CLI unavailable
                creds = self.authenticator.authenticate()
                self.assertIsNotNone(creds)


class TestCLIInterface(unittest.TestCase):
    """Test command-line interface functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_cli_authentication_command(self):
        """Test CLI authentication command."""
        from bsr_auth import main
        
        with patch('sys.argv', ['bsr_auth.py', '--cache-dir', str(self.temp_dir), 'auth', '--method', 'environment']):
            with patch.dict(os.environ, {'BUF_TOKEN': 'cli_test_token_123456'}):
                with patch('bsr_auth.subprocess.run') as mock_subprocess:
                    mock_subprocess.return_value.returncode = 0
                    
                    with patch('builtins.print') as mock_print:
                        result = main()
                        self.assertEqual(result, 0)
                        
                        # Verify success message was printed
                        print_calls = [call[0][0] for call in mock_print.call_args_list]
                        success_msg = any("Successfully authenticated" in msg for msg in print_calls)
                        self.assertTrue(success_msg)
    
    def test_cli_status_command(self):
        """Test CLI status command."""
        from bsr_auth import main
        
        # First authenticate
        authenticator = BSRAuthenticator(cache_dir=self.temp_dir)
        with patch.dict(os.environ, {'BUF_TOKEN': 'cli_status_test_token'}):
            with patch('bsr_auth.subprocess.run') as mock_subprocess:
                mock_subprocess.return_value.returncode = 0
                authenticator.authenticate()
        
        # Then check status
        with patch('sys.argv', ['bsr_auth.py', '--cache-dir', str(self.temp_dir), 'status']):
            with patch('builtins.print') as mock_print:
                result = main()
                self.assertEqual(result, 0)
                
                # Verify authenticated status was printed
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                auth_msg = any("✅ Authenticated" in msg for msg in print_calls)
                self.assertTrue(auth_msg)


def run_comprehensive_tests():
    """Run all BSR authentication tests."""
    test_suites = [
        unittest.TestLoader().loadTestsFromTestCase(TestBSRCredentials),
        unittest.TestLoader().loadTestsFromTestCase(TestBSRCredentialManager),
        unittest.TestLoader().loadTestsFromTestCase(TestBSRAuthenticator),
        unittest.TestLoader().loadTestsFromTestCase(TestSecurityFeatures),
        unittest.TestLoader().loadTestsFromTestCase(TestIntegrationPatterns),
        unittest.TestLoader().loadTestsFromTestCase(TestCLIInterface),
    ]
    
    combined_suite = unittest.TestSuite(test_suites)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(combined_suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    print("🔐 Running BSR Authentication System Tests")
    print("=" * 50)
    
    success = run_comprehensive_tests()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All tests passed! BSR Authentication System is working correctly.")
    else:
        print("❌ Some tests failed. Please check the output above.")
    
    exit(0 if success else 1)
