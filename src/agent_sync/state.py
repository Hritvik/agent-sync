"""State tracking for managed servers."""

import json
from pathlib import Path

from pydantic import ValidationError

from agent_sync.exceptions import ConfigNotFoundError
from agent_sync.models import ClientState, State
from agent_sync.paths import get_state_path


def load_state(path: Path | None = None) -> State:
    """Load state from JSON file."""
    if path is None:
        path = get_state_path()

    if not path.exists():
        # Return empty state if file doesn't exist
        return State()

    with open(path, "r") as f:
        data = json.load(f)

    if data is None:
        return State()

    try:
        return State.model_validate(data)
    except ValidationError as e:
        # If state is corrupted, return empty state
        # This is safer than failing completely
        return State()


def save_state(state: State, path: Path | None = None) -> None:
    """Save state to JSON file."""
    if path is None:
        path = get_state_path()

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict for JSON serialization
    data = state.model_dump(mode="python", exclude_none=True)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def update_client_state(
    client_name: str,
    config_path: str,
    managed_servers: dict[str, str],
    mcp_sync_version: str | None = None,
    path: Path | None = None,
) -> None:
    """Update state for a specific client."""
    state = load_state(path)

    if client_name not in state.clients:
        state.clients[client_name] = ClientState(config_path=config_path)

    client_state = state.clients[client_name]
    client_state.config_path = config_path
    client_state.managed_servers = managed_servers
    client_state.mcp_sync_version = mcp_sync_version

    from datetime import datetime, timezone

    client_state.last_applied = datetime.now(timezone.utc).isoformat()

    save_state(state, path)


def get_client_state(client_name: str, path: Path | None = None) -> ClientState | None:
    """Get state for a specific client."""
    state = load_state(path)
    return state.clients.get(client_name)


def is_server_managed(client_name: str, server_name: str, path: Path | None = None) -> bool:
    """Check if a server is managed by mcp-sync for a specific client."""
    client_state = get_client_state(client_name, path)
    if client_state is None:
        return False
    return server_name in client_state.managed_servers


def remove_server_from_state(client_name: str, server_name: str, path: Path | None = None) -> None:
    """Remove a server from managed state."""
    state = load_state(path)

    if client_name not in state.clients:
        return

    client_state = state.clients[client_name]
    if server_name in client_state.managed_servers:
        del client_state.managed_servers[server_name]

    save_state(state, path)


def clear_client_state(client_name: str, path: Path | None = None) -> None:
    """Clear all state for a specific client."""
    state = load_state(path)

    if client_name in state.clients:
        del state.clients[client_name]

    save_state(state, path)
