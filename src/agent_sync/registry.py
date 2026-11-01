"""Registry loading and validation logic."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from agent_sync.exceptions import ConfigNotFoundError, ValidationError as McpSyncValidationError
from agent_sync.models import Profiles, Registry
from agent_sync.paths import get_profiles_path, get_servers_path


def load_registry(path: Path | None = None) -> Registry:
    """Load the canonical MCP server registry from YAML."""
    if path is None:
        path = get_servers_path()

    if not path.exists():
        raise ConfigNotFoundError(str(path))

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    try:
        return Registry.model_validate(data)
    except ValidationError as e:
        # Convert Pydantic ValidationError to our custom ValidationError
        error_details = e.errors()[0]
        server_name = None
        field = str(error_details["loc"][0]) if error_details["loc"] else None
        
        # Try to extract server name from location
        if "servers" in error_details["loc"]:
            idx = error_details["loc"].index("servers")
            if idx + 1 < len(error_details["loc"]):
                server_name = error_details["loc"][idx + 1]
        
        raise McpSyncValidationError(
            message=error_details["msg"],
            server_name=server_name,
            field=field,
        ) from e


def load_profiles(path: Path | None = None) -> Profiles:
    """Load profile definitions from YAML."""
    if path is None:
        path = get_profiles_path()

    if not path.exists():
        # Return empty profiles if file doesn't exist
        return Profiles()

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        return Profiles()

    try:
        return Profiles.model_validate(data)
    except ValidationError as e:
        error_details = e.errors()[0]
        raise McpSyncValidationError(
            message=f"Invalid profiles configuration: {error_details['msg']}",
            field=str(error_details["loc"][0]) if error_details["loc"] else None,
        ) from e


def save_registry(registry: Registry, path: Path | None = None) -> None:
    """Save the canonical MCP server registry to YAML."""
    if path is None:
        path = get_servers_path()

    # Convert to dict for YAML serialization
    data = registry.model_dump(mode="python", exclude_none=True)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def save_profiles(profiles: Profiles, path: Path | None = None) -> None:
    """Save profile definitions to YAML."""
    if path is None:
        path = get_profiles_path()

    # Convert to dict for YAML serialization
    data = profiles.model_dump(mode="python", exclude_none=True)

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def filter_servers_by_profile(registry: Registry, profiles: Profiles, profile_name: str) -> Registry:
    """Filter registry servers based on a profile."""
    if profile_name not in profiles.profiles:
        raise ValueError(f"Profile not found: {profile_name}")

    profile = profiles.profiles[profile_name]
    filtered_servers = {}

    for server_name in profile.servers:
        if server_name not in registry.servers:
            raise ValueError(f"Server '{server_name}' in profile '{profile_name}' not found in registry")
        filtered_servers[server_name] = registry.servers[server_name]

    # Create a new registry with filtered servers
    return Registry(
        version=registry.version,
        defaults=registry.defaults,
        servers=filtered_servers,
    )


def filter_servers_by_client(registry: Registry, client_name: str) -> Registry:
    """Filter registry servers based on client inclusion/exclusion."""
    filtered_servers = {}

    for server_name, server_def in registry.servers.items():
        # Check if server is explicitly excluded for this client
        if server_def.clients.exclude and client_name in server_def.clients.exclude:
            continue

        # Check if server has an include list and client is not in it
        if server_def.clients.include and client_name not in server_def.clients.include:
            continue

        # Server is available for this client
        filtered_servers[server_name] = server_def

    return Registry(
        version=registry.version,
        defaults=registry.defaults,
        servers=filtered_servers,
    )
