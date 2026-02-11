"""Encryption utilities for sensitive config fields."""

import base64
import os
import re
from typing import Any

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Sensitive field patterns to encrypt
SENSITIVE_FIELD_PATTERNS = [
    r"api_key",
    r"secret",
    r"password",
    r"token",
    r"credential",
    r"private_key",
    r"access_key",
]


class ConfigEncryption:
    """Handles encryption/decryption of sensitive config fields."""

    def __init__(self, secret_key: str | None = None):
        """Initialize encryption with secret key.

        Args:
            secret_key: Base secret for encryption (from env var or settings)
        """
        # Use provided key or get from environment
        key_material = secret_key or os.environ.get("CONFIG_ENCRYPTION_KEY")
        if not key_material:
            raise ValueError(
                "CONFIG_ENCRYPTION_KEY environment variable must be set for config encryption"
            )

        # Derive a proper Fernet key from the secret
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"amplifier-config-salt",  # In production, use unique salt per deployment
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key_material.encode()))
        self.fernet = Fernet(key)

    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field name indicates sensitive data."""
        field_lower = field_name.lower()
        return any(re.search(pattern, field_lower) for pattern in SENSITIVE_FIELD_PATTERNS)

    def _is_encrypted(self, value: str) -> bool:
        """Check if value is already encrypted (has our prefix)."""
        return value.startswith("enc:")

    def _is_env_var_reference(self, value: str) -> bool:
        """Check if value is an environment variable reference."""
        return value.startswith("${") and value.endswith("}")

    def encrypt_config(self, config_dict: dict[str, Any], path: str = "") -> dict[str, Any]:
        """Recursively encrypt sensitive fields in config.

        Args:
            config_dict: Config dictionary to process
            path: Current path in config (for logging)

        Returns:
            Config with sensitive fields encrypted
        """
        if isinstance(config_dict, dict):
            result = {}
            for key, value in config_dict.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, str):
                    # Skip if already encrypted or is env var reference
                    if self._is_encrypted(value) or self._is_env_var_reference(value):
                        result[key] = value
                    # Encrypt if sensitive field
                    elif self._is_sensitive_field(key) and value:
                        encrypted = self.fernet.encrypt(value.encode())
                        result[key] = f"enc:{encrypted.decode()}"
                    else:
                        result[key] = value

                elif isinstance(value, dict):
                    result[key] = self.encrypt_config(value, current_path)

                elif isinstance(value, list):
                    result[key] = [
                        self.encrypt_config(item, f"{current_path}[{i}]")
                        if isinstance(item, dict)
                        else item
                        for i, item in enumerate(value)
                    ]
                else:
                    result[key] = value

            return result

        return config_dict

    def decrypt_config(self, config_dict: dict[str, Any], path: str = "") -> dict[str, Any]:
        """Recursively decrypt sensitive fields in config.

        Args:
            config_dict: Config dictionary to process
            path: Current path in config (for logging)

        Returns:
            Config with sensitive fields decrypted
        """
        if isinstance(config_dict, dict):
            result = {}
            for key, value in config_dict.items():
                current_path = f"{path}.{key}" if path else key

                if isinstance(value, str) and self._is_encrypted(value):
                    # Remove prefix and decrypt
                    encrypted_data = value[4:]  # Remove "enc:" prefix
                    try:
                        decrypted = self.fernet.decrypt(encrypted_data.encode())
                        result[key] = decrypted.decode()
                    except Exception as e:
                        raise ValueError(f"Failed to decrypt field {current_path}: {e}") from e

                elif isinstance(value, dict):
                    result[key] = self.decrypt_config(value, current_path)

                elif isinstance(value, list):
                    result[key] = [
                        self.decrypt_config(item, f"{current_path}[{i}]")
                        if isinstance(item, dict)
                        else item
                        for i, item in enumerate(value)
                    ]
                else:
                    result[key] = value

            return result

        return config_dict
