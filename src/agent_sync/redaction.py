"""Secret handling and redaction utilities."""

import os
import re
from typing import Any

# Patterns that suggest a value might be a secret
SECRET_PATTERNS = [
    r".*token.*",
    r".*secret.*",
    r".*password.*",
    r".*api[_-]?key.*",
    r".*private[_-]?key.*",
    r".*auth[_-]?token.*",
    r".*access[_-]?token.*",
    r".*session[_-]?key.*",
    r".*credential.*",
]

# Patterns for common secret values
SECRET_VALUE_PATTERNS = [
    r"^sk-[a-zA-Z0-9]{32,}$",  # OpenAI-style keys
    r"^Bearer [a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$",  # JWT
    r"^[a-fA-F0-9]{32,}$",  # Hex strings (likely keys)
    r"^ghp_[a-zA-Z0-9]{36,}$",  # GitHub personal access tokens
    r"^xox[bap]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-zA-Z0-9]{32}$",  # Slack tokens
]


def looks_like_secret(key: str) -> bool:
    """Check if a key name suggests it might contain a secret."""
    key_lower = key.lower()
    for pattern in SECRET_PATTERNS:
        if re.match(pattern, key_lower):
            return True
    return False


def looks_like_secret_value(value: str) -> bool:
    """Check if a value looks like a secret."""
    if not isinstance(value, str) or len(value) < 16:
        return False
    
    for pattern in SECRET_VALUE_PATTERNS:
        if re.match(pattern, value):
            return True
    
    return False


def redact_value(value: Any, key: str | None = None) -> str:
    """Redact a value if it appears to be a secret.

    Args:
        value: The value to potentially redact
        key: The key name (helps determine if value should be redacted)

    Returns:
        The redacted value or the original value if it doesn't look like a secret
    """
    if not isinstance(value, str):
        return str(value)
    
    # Always redact if key suggests it's a secret
    if key and looks_like_secret(key):
        return "***REDACTED***"
    
    # Redact if value looks like a secret
    if looks_like_secret_value(value):
        return "***REDACTED***"
    
    return value


def redact_dict(data: dict[str, Any], sensitive_keys: set[str] | None = None) -> dict[str, Any]:
    """Redact secret values in a dictionary.

    Args:
        data: The dictionary to redact
        sensitive_keys: Additional keys to always redact

    Returns:
        A new dictionary with secrets redacted
    """
    if sensitive_keys is None:
        sensitive_keys = set()
    
    result = {}
    
    for key, value in data.items():
        if key in sensitive_keys or looks_like_secret(key):
            result[key] = "***REDACTED***"
        elif isinstance(value, dict):
            result[key] = redact_dict(value, sensitive_keys)
        elif isinstance(value, list):
            result[key] = redact_list(value, sensitive_keys)
        else:
            result[key] = redact_value(value, key)
    
    return result


def redact_list(data: list[Any], sensitive_keys: set[str] | None = None) -> list[Any]:
    """Redact secret values in a list.

    Args:
        data: The list to redact
        sensitive_keys: Additional keys to always redact

    Returns:
        A new list with secrets redacted
    """
    if sensitive_keys is None:
        sensitive_keys = set()
    
    result = []
    
    for item in data:
        if isinstance(item, dict):
            result.append(redact_dict(item, sensitive_keys))
        elif isinstance(item, list):
            result.append(redact_list(item, sensitive_keys))
        else:
            result.append(redact_value(item))
    
    return result


def check_env_vars_exist(env_refs: set[str]) -> list[str]:
    """Check which environment variables are missing.

    Args:
        env_refs: Set of environment variable names to check

    Returns:
        List of missing environment variable names
    """
    missing = []
    for var_name in env_refs:
        if var_name not in os.environ:
            missing.append(var_name)
    return missing


def extract_env_references(config: dict[str, Any]) -> set[str]:
    """Extract all environment variable references from a configuration.

    Args:
        config: The configuration to scan

    Returns:
        Set of environment variable names referenced
    """
    refs = set()
    
    def scan(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                # Check for from_env pattern
                if isinstance(value, dict) and "from_env" in value:
                    refs.add(value["from_env"])
                else:
                    scan(value)
        elif isinstance(obj, list):
            for item in obj:
                scan(item)
    
    scan(config)
    return refs


def warn_about_secrets(config: dict[str, Any]) -> list[str]:
    """Generate warnings about potential secrets in configuration.

    Args:
        config: The configuration to check

    Returns:
        List of warning messages
    """
    warnings = []
    
    def scan(obj: Any, path: str = "") -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check for literal values that look like secrets
                if isinstance(value, str) and looks_like_secret_value(value):
                    warnings.append(
                        f"Potential secret value at '{current_path} - consider using environment variable reference instead"
                    )
                elif isinstance(value, dict):
                    # Check for from_env pattern (this is good, no warning)
                    if "from_env" not in value:
                        scan(value, current_path)
                else:
                    scan(value, current_path)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                scan(item, f"{path}[{i}]")
    
    scan(config)
    return warnings
