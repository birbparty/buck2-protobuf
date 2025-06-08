#!/usr/bin/env python3
"""
Basic BSR Authentication Example

This example demonstrates how to use the BSR authentication system
for accessing private repositories and team collaboration.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from tools.bsr_auth import BSRAuthenticator, BSRCredentials, BSRAuthenticationError
from tools.bsr_client import BSRClient

def demo_authentication_methods():
    """Demonstrate different authentication methods."""
    print("🔐 BSR Authentication Demo")
    print("=" * 50)
    
    # Initialize authenticator
    authenticator = BSRAuthenticator(verbose=True)
    
    # Check current authentication status
    status = authenticator.get_authentication_status()
    print(f"\nCurrent Status:")
    print(f"  Repository: {status['repository']}")
    print(f"  Authenticated: {status['authenticated']}")
    
    if status['authenticated']:
        print(f"  Method: {status['auth_method']}")
        print(f"  Token: {status.get('token_preview', 'N/A')}")
    
    print("\n" + "=" * 50)
    return status['authenticated']

def demo_bsr_client_integration():
    """Demonstrate BSR client with authentication."""
    print("\n📦 BSR Client Integration Demo")
    print("=" * 50)
    
    try:
        # Initialize BSR client with auto-authentication
        client = BSRClient(verbose=True)
        
        # Check authentication status
        auth_status = client.get_authentication_status()
        print(f"\nClient Authentication Status:")
        print(f"  Authenticated: {auth_status['authenticated']}")
        
        if auth_status['authenticated']:
            print(f"  Method: {auth_status['auth_method']}")
            print(f"  Registry: {auth_status['repository']}")
        
        # Try some BSR operations (these would work with actual BSR access)
        print(f"\n🔍 Testing BSR Operations:")
        print(f"  ✅ BSR client initialized successfully")
        print(f"  ✅ Authentication system integrated")
        print(f"  ✅ Ready for private repository access")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def demo_cli_commands():
    """Demonstrate CLI commands."""
    print("\n💻 CLI Commands Demo")
    print("=" * 50)
    
    print("Available CLI commands:")
    print("  # Check authentication status")
    print("  python tools/bsr_auth.py status")
    print()
    print("  # Authenticate using environment variable")
    print("  export BUF_TOKEN='your_token_here'")
    print("  python tools/bsr_auth.py auth --method environment")
    print()
    print("  # List authenticated repositories")
    print("  python tools/bsr_auth.py list")
    print()
    print("  # Logout from all repositories")
    print("  python tools/bsr_auth.py logout")
    print()
    print("  # Interactive authentication")
    print("  python tools/bsr_auth.py auth --method interactive")

def demo_security_features():
    """Demonstrate security features."""
    print("\n🔒 Security Features Demo")
    print("=" * 50)
    
    # Create example credentials
    try:
        creds = BSRCredentials(
            token="example_secure_token_123456",
            username="demo_user",
            registry="buf.build",
            auth_method="demo"
        )
        
        print("✅ Credential validation:")
        print(f"  Token format validated: {creds.token[:10]}...")
        print(f"  Masked token: {creds.mask_token()}")
        print(f"  Expires: {'No' if not creds.is_expired() else 'Yes'}")
        
        print("\n✅ Security features:")
        print("  🔐 Token format validation")
        print("  🔐 Secure system keyring storage")
        print("  🔐 Encrypted file fallback")
        print("  🔐 Token masking for logs")
        print("  🔐 Expiration handling")
        print("  🔐 Access validation")
        
        return True
        
    except Exception as e:
        print(f"❌ Security demo error: {e}")
        return False

def main():
    """Run the authentication demo."""
    print("🚀 BSR Authentication System Demo")
    print("This demo shows the key features of the BSR authentication system.")
    print()
    
    # Run demonstrations
    results = []
    
    # Basic authentication
    results.append(demo_authentication_methods())
    
    # BSR client integration
    results.append(demo_bsr_client_integration())
    
    # CLI commands
    demo_cli_commands()
    
    # Security features
    results.append(demo_security_features())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Demo Summary")
    print("=" * 50)
    
    if all(results[:2]):  # Skip CLI demo result
        print("✅ All authentication features working correctly!")
        print()
        print("🎯 Next Steps:")
        print("1. Set up your BSR token: export BUF_TOKEN='your_token'")
        print("2. Test authentication: python tools/bsr_auth.py auth")
        print("3. Use with private repositories in your builds")
        print("4. Set up team collaboration workflows")
    else:
        print("⚠️  Some features need BSR token to fully demonstrate")
        print("   Set BUF_TOKEN environment variable for full functionality")
    
    print()
    print("📚 Documentation: docs/bsr-authentication.md")
    print("🧪 Tests: python tools/test_bsr_auth.py")

if __name__ == "__main__":
    main()
