"""Example demonstrating config encryption workflow for apps.

This example shows how CLI/Web/Desktop apps should:
1. Encrypt API keys before sending configs to the API
2. Retrieve configs with encrypted keys
3. Decrypt keys locally when needed
"""

import os

import requests

# NOTE: In a real app, import from a shared amplifier-nexus package
# For now, we'll define a simple client-side encryption class
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64


class ClientEncryption:
    """Client-side encryption for apps."""

    def __init__(self, secret_key: str):
        """Initialize with encryption key from environment."""
        # Derive Fernet key (same as server)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"amplifier-config-salt",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        self.fernet = Fernet(key)

    def encrypt_value(self, value: str) -> str:
        """Encrypt a single value."""
        encrypted = self.fernet.encrypt(value.encode())
        return f"enc:{encrypted.decode()}"

    def decrypt_value(self, value: str) -> str:
        """Decrypt a single value."""
        if not value.startswith("enc:"):
            return value
        encrypted_data = value[4:]  # Remove "enc:" prefix
        decrypted = self.fernet.decrypt(encrypted_data.encode())
        return decrypted.decode()


# Configuration
API_BASE_URL = os.environ.get("AMPLIFIER_API_URL", "http://localhost:8000")
API_KEY = os.environ.get("AMPLIFIER_API_KEY", "test-api-key")
JWT_TOKEN = os.environ.get("AMPLIFIER_JWT_TOKEN", "test-jwt-token")
ENCRYPTION_KEY = os.environ.get("CONFIG_ENCRYPTION_KEY")


def get_headers():
    """Get API request headers."""
    return {
        "X-API-Key": API_KEY,
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json",
    }


# ==============================================================================
# Example 1: Create config with app-side encryption (RECOMMENDED)
# ==============================================================================


def example_1_create_with_app_encryption():
    """Create a config with API key encrypted by the app."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Create config with app-side encryption (RECOMMENDED)")
    print("=" * 80)

    # Initialize encryption
    encryptor = ClientEncryption(ENCRYPTION_KEY)

    # Your plain API key
    plain_api_key = "sk-ant-abc123-my-secret-key"

    # Encrypt before sending
    encrypted_api_key = encryptor.encrypt_value(plain_api_key)
    print(f"\nPlain API key: {plain_api_key}")
    print(f"Encrypted API key: {encrypted_api_key[:50]}...")

    # Create config with encrypted key
    config = {
        "name": "my-secure-config",
        "description": "Config with app-encrypted API key",
        "config_data": {
            "bundle": {"name": "my-config", "version": "1.0.0"},
            "providers": [
                {
                    "module": "provider-anthropic",
                    "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                    "config": {"api_key": encrypted_api_key, "model": "claude-sonnet-4-5"},
                }
            ],
        },
    }

    # Send to API
    response = requests.post(f"{API_BASE_URL}/configs", json=config, headers=get_headers())

    if response.status_code == 201:
        config_data = response.json()
        print(f"\n✅ Config created: {config_data['config_id']}")
        print(f"   Encrypted flag: {config_data.get('encrypted', False)}")
        return config_data["config_id"]
    else:
        print(f"\n❌ Failed to create config: {response.status_code}")
        print(f"   {response.text}")
        return None


# ==============================================================================
# Example 2: Create config without app-side encryption (service encrypts)
# ==============================================================================


def example_2_create_without_app_encryption():
    """Create a config with plain API key - service will encrypt it."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Create config without app-side encryption (service encrypts)")
    print("=" * 80)

    # Send plain API key - service will encrypt it
    plain_api_key = "sk-ant-xyz789-another-key"
    print(f"\nSending plain API key: {plain_api_key}")

    config = {
        "name": "my-plain-config",
        "description": "Config with plain API key (service encrypts)",
        "config_data": {
            "bundle": {"name": "my-config", "version": "1.0.0"},
            "providers": [
                {
                    "module": "provider-anthropic",
                    "source": "git+https://github.com/microsoft/amplifier-module-provider-anthropic@main",
                    "config": {"api_key": plain_api_key, "model": "claude-sonnet-4-5"},
                }
            ],
        },
    }

    response = requests.post(f"{API_BASE_URL}/configs", json=config, headers=get_headers())

    if response.status_code == 201:
        config_data = response.json()
        print(f"\n✅ Config created: {config_data['config_id']}")
        print(f"   Service encrypted the API key before storage")
        return config_data["config_id"]
    else:
        print(f"\n❌ Failed to create config: {response.status_code}")
        print(f"   {response.text}")
        return None


# ==============================================================================
# Example 3: Retrieve config with encrypted keys (DEFAULT - Secure)
# ==============================================================================


def example_3_retrieve_encrypted(config_id: str):
    """Retrieve config with encrypted keys (secure for apps)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Retrieve config with encrypted keys (DEFAULT - Secure)")
    print("=" * 80)

    # Get config WITHOUT decryption (default behavior)
    response = requests.get(
        f"{API_BASE_URL}/configs/{config_id}?decrypt=false", headers=get_headers()
    )

    if response.status_code == 200:
        config_data = response.json()
        api_key = config_data["config_data"]["providers"][0]["config"]["api_key"]

        print(f"\n✅ Config retrieved: {config_id}")
        print(f"   Encrypted flag: {config_data.get('encrypted', False)}")
        print(f"   API key (encrypted): {api_key[:50]}...")
        print(f"\n   ℹ️  Key is encrypted - safe to transmit over network")

        return api_key
    else:
        print(f"\n❌ Failed to retrieve config: {response.status_code}")
        return None


# ==============================================================================
# Example 4: Decrypt keys locally in the app
# ==============================================================================


def example_4_decrypt_locally(encrypted_api_key: str):
    """Decrypt API key locally in the app."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Decrypt API key locally in the app")
    print("=" * 80)

    # Initialize encryption
    encryptor = ClientEncryption(ENCRYPTION_KEY)

    # Decrypt the key
    plain_api_key = encryptor.decrypt_value(encrypted_api_key)

    print(f"\nEncrypted API key: {encrypted_api_key[:50]}...")
    print(f"Decrypted API key: {plain_api_key}")
    print(f"\n   ℹ️  Now you can use the plain key in your app")

    return plain_api_key


# ==============================================================================
# Example 5: Retrieve config with decrypted keys (ADMIN/DEBUG ONLY)
# ==============================================================================


def example_5_retrieve_decrypted(config_id: str):
    """Retrieve config with decrypted keys (use with caution)."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Retrieve config with decrypted keys (ADMIN/DEBUG ONLY)")
    print("=" * 80)

    # Get config WITH decryption (for debugging/admin)
    response = requests.get(
        f"{API_BASE_URL}/configs/{config_id}?decrypt=true", headers=get_headers()
    )

    if response.status_code == 200:
        config_data = response.json()
        api_key = config_data["config_data"]["providers"][0]["config"]["api_key"]

        print(f"\n✅ Config retrieved: {config_id}")
        print(f"   Encrypted flag: {config_data.get('encrypted', False)}")
        print(f"   API key (decrypted): {api_key}")
        print(f"\n   ⚠️  WARNING: Decrypted key exposed via API - use with caution!")

        return api_key
    else:
        print(f"\n❌ Failed to retrieve config: {response.status_code}")
        return None


# ==============================================================================
# Example 6: Complete workflow
# ==============================================================================


def example_6_complete_workflow():
    """Demonstrate complete encryption workflow."""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Complete secure workflow")
    print("=" * 80)

    encryptor = ClientEncryption(ENCRYPTION_KEY)

    # Step 1: App has plain API key (from user input or settings)
    plain_key = "sk-ant-secure-workflow-key"
    print(f"\n1️⃣  App has plain API key: {plain_key}")

    # Step 2: Encrypt before sending to API
    encrypted_key = encryptor.encrypt_value(plain_key)
    print(f"2️⃣  App encrypts key: {encrypted_key[:50]}...")

    # Step 3: Send encrypted config to API
    config = {
        "name": "secure-workflow-config",
        "config_data": {
            "bundle": {"name": "my-config", "version": "1.0.0"},
            "providers": [{"config": {"api_key": encrypted_key}}],
        },
    }
    response = requests.post(f"{API_BASE_URL}/configs", json=config, headers=get_headers())
    config_id = response.json()["config_id"] if response.status_code == 201 else None
    print(f"3️⃣  Config created in API: {config_id}")

    # Step 4: Later, retrieve config (stays encrypted)
    response = requests.get(
        f"{API_BASE_URL}/configs/{config_id}?decrypt=false", headers=get_headers()
    )
    retrieved_key = response.json()["config_data"]["providers"][0]["config"]["api_key"]
    print(f"4️⃣  Retrieved encrypted key: {retrieved_key[:50]}...")

    # Step 5: Decrypt locally when needed
    decrypted_key = encryptor.decrypt_value(retrieved_key)
    print(f"5️⃣  Decrypted locally: {decrypted_key}")

    # Verify it matches
    assert decrypted_key == plain_key, "Decrypted key should match original!"
    print(f"\n✅ Complete workflow successful!")
    print(f"   - Key encrypted before sending")
    print(f"   - Stored encrypted in database")
    print(f"   - Retrieved encrypted from API")
    print(f"   - Decrypted locally in app")


# ==============================================================================
# Main
# ==============================================================================


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("API KEY ENCRYPTION EXAMPLES")
    print("=" * 80)
    print(f"\nAPI Base URL: {API_BASE_URL}")
    print(f"Encryption Key: {'✅ Set' if ENCRYPTION_KEY else '❌ Not set'}")

    if not ENCRYPTION_KEY:
        print("\n⚠️  WARNING: CONFIG_ENCRYPTION_KEY not set!")
        print("   Set it with: export CONFIG_ENCRYPTION_KEY='your-secret-key'")
        return

    try:
        # Example 1: App-side encryption (recommended)
        config_id_1 = example_1_create_with_app_encryption()

        # Example 2: Service-side encryption
        config_id_2 = example_2_create_without_app_encryption()

        if config_id_1:
            # Example 3: Retrieve encrypted
            encrypted_key = example_3_retrieve_encrypted(config_id_1)

            if encrypted_key:
                # Example 4: Decrypt locally
                example_4_decrypt_locally(encrypted_key)

            # Example 5: Retrieve decrypted (admin/debug)
            example_5_retrieve_decrypted(config_id_1)

        # Example 6: Complete workflow
        example_6_complete_workflow()

    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
