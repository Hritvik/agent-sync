"""Merge logic for preserving non-MCP settings in client configurations."""

import json
from typing import Any

from agent_sync.exceptions import ConflictError
from agent_sync.state import is_server_managed


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries.

    Args:
        base: The base dictionary to merge into
        update: The dictionary with updates to apply

    Returns:
        A new dictionary with the merged result
    """
    result = base.copy()

    for key, value in update.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # For lists, replace entirely (don't merge)
                result[key] = value
            else:
                # For scalar values, update takes precedence
                result[key] = value
        else:
            result[key] = value

    return result


def merge_mcp_config(
    existing: dict[str, Any],
    generated: dict[str, Any],
    mcp_key: str,
    client_name: str,
    managed_servers: set[str] | None = None,
) -> dict[str, Any]:
    """Merge MCP server configuration while preserving non-MCP settings.

    Args:
        existing: The existing client configuration
        generated: The generated MCP configuration from the registry
        mcp_key: The key used for MCP servers in this client's config (e.g., "mcpServers", "servers")
        client_name: The name of the client for state tracking
        managed_servers: Set of server names that are managed by mcp-sync

    Returns:
        The merged configuration

    Raises:
        ConflictError: If a conflict is detected between existing and generated config
    """
    if managed_servers is None:
        managed_servers = set()

    result = existing.copy()

    # Extract existing MCP servers
    existing_mcp = existing.get(mcp_key, {})
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    # Extract generated MCP servers
    generated_mcp = generated.get(mcp_key, {})
    if not isinstance(generated_mcp, dict):
        generated_mcp = {}

    # Build the merged MCP configuration
    merged_mcp = {}

    # First, preserve unmanaged servers from existing config
    for server_name, server_config in existing_mcp.items():
        if server_name not in managed_servers:
            # This server is not managed by mcp-sync, preserve it
            merged_mcp[server_name] = server_config

    # Then, add/update managed servers from generated config
    for server_name, server_config in generated_mcp.items():
        if server_name in existing_mcp:
            # Server exists in both configs
            if server_name in managed_servers:
                # This is a managed server, update it
                merged_mcp[server_name] = server_config
            else:
                # Server exists but is not managed - this is a conflict
                existing_config = existing_mcp[server_name]
                if existing_config != server_config:
                    raise ConflictError(
                        message=f"Server '{server_name}' already exists in {client_name} configuration with different settings",
                        server_name=server_name,
                        client=client_name,
                        existing_config=existing_config,
                        new_config=server_config,
                    )
                else:
                    # Configs are identical, no conflict
                    merged_mcp[server_name] = server_config
        else:
            # New server, add it
            merged_mcp[server_name] = server_config

    # Remove managed servers that were deleted from the registry
    for server_name in managed_servers:
        if server_name in existing_mcp and server_name not in generated_mcp:
            # This managed server was removed from the registry, remove it from config
            pass  # Already handled by not including it in merged_mcp

    # Update the result with the merged MCP configuration
    result[mcp_key] = merged_mcp

    # Deep merge any other top-level keys from generated config
    for key, value in generated.items():
        if key != mcp_key and key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        elif key != mcp_key:
            result[key] = value

    return result


def detect_conflicts(
    existing: dict[str, Any],
    generated: dict[str, Any],
    mcp_key: str,
    client_name: str,
    managed_servers: set[str],
) -> list[ConflictError]:
    """Detect conflicts between existing and generated configurations.

    Args:
        existing: The existing client configuration
        generated: The generated MCP configuration from the registry
        mcp_key: The key used for MCP servers in this client's config
        client_name: The name of the client
        managed_servers: Set of server names that are managed by mcp-sync

    Returns:
        List of ConflictError objects for each conflict detected
    """
    conflicts = []

    existing_mcp = existing.get(mcp_key, {})
    if not isinstance(existing_mcp, dict):
        existing_mcp = {}

    generated_mcp = generated.get(mcp_key, {})
    if not isinstance(generated_mcp, dict):
        generated_mcp = {}

    for server_name in existing_mcp:
        if server_name in generated_mcp:
            if server_name not in managed_servers:
                # Server exists in both but is not managed
                existing_config = existing_mcp[server_name]
                generated_config = generated_mcp[server_name]
                if existing_config != generated_config:
                    conflicts.append(
                        ConflictError(
                            message=f"Server '{server_name}' already exists in {client_name} configuration with different settings",
                            server_name=server_name,
                            client=client_name,
                            existing_config=existing_config,
                            new_config=generated_config,
                        )
                    )

    return conflicts


def configs_are_equal(config1: dict[str, Any], config2: dict[str, Any]) -> bool:
    """Check if two configurations are equal.

    Args:
        config1: First configuration
        config2: Second configuration

    Returns:
        True if the configurations are equal, False otherwise
    """
    # Use JSON serialization for comparison to handle ordering differences
    return json.dumps(config1, sort_keys=True) == json.dumps(config2, sort_keys=True)
