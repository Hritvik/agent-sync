"""Codex (OpenAI) MCP client adapter."""

import shutil
from pathlib import Path
from typing import Any

import tomlkit
from tomlkit.items import Table

from agent_sync.adapters.base import BaseAdapter
from agent_sync.backup import compute_config_hash, write_atomically
from agent_sync.exceptions import AdapterError, UnsupportedFeatureError
from agent_sync.models import (
    EnvValue,
    EnvValueLiteral,
    EnvValueSource,
    HttpServerConfig,
    Registry,
    SseServerConfig,
    StdioServerConfig,
    TransportType,
    WsServerConfig,
)
from agent_sync.redaction import redact_dict


class CodexAdapter(BaseAdapter):
    """Adapter for Codex (OpenAI) MCP configuration."""

    name = "codex"

    def detect(self) -> bool:
        """Check if Codex appears to be installed."""
        # Check for Codex config directory
        config_path = Path.home() / ".codex"
        return config_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for Codex."""
        if scope == "user":
            return Path.home() / ".codex" / "config.toml"
        elif scope == "project":
            return Path.cwd() / ".codex" / "config.toml"
        else:
            raise AdapterError(f"Unsupported scope for Codex: {scope}", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the Codex configuration."""
        path = self.config_path(scope)

        if not path.exists():
            # Return empty config if file doesn't exist
            return {}

        try:
            with open(path, "r") as f:
                data = tomlkit.load(f)
            
            # Convert to dict for easier manipulation
            return dict(data)
        except Exception as e:
            raise AdapterError(f"Failed to load Codex config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to Codex-specific TOML format."""
        result: dict[str, Any] = {"mcp_servers": {}}

        for server_name, server_def in registry.servers.items():
            if not server_def.enabled:
                continue

            server_config: dict[str, Any] = {}

            # Handle different transport types
            if isinstance(server_def.config, StdioServerConfig):
                server_config["command"] = server_def.config.command
                if server_def.config.args:
                    server_config["args"] = server_def.config.args
                if server_def.config.cwd:
                    server_config["cwd"] = server_def.config.cwd
                
                # Handle environment variables
                if server_def.config.env:
                    env_dict = {}
                    env_vars_list = []
                    for key, value in server_def.config.env.items():
                        if isinstance(value, EnvValueSource):
                            # Use env_vars for environment references
                            env_vars_list.append(key)
                        elif isinstance(value, EnvValueLiteral):
                            # Use env for literal values
                            env_dict[key] = value.value
                    
                    if env_dict:
                        server_config["env"] = env_dict
                    if env_vars_list:
                        server_config["env_vars"] = env_vars_list

            elif isinstance(server_def.config, HttpServerConfig):
                server_config["url"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    http_headers = {}
                    env_http_headers = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueSource):
                            env_http_headers[key] = value.from_env
                        elif isinstance(value, EnvValueLiteral):
                            http_headers[key] = value.value
                    
                    if http_headers:
                        server_config["http_headers"] = http_headers
                    if env_http_headers:
                        server_config["env_http_headers"] = env_http_headers

            else:
                # SSE and WS are not supported by Codex
                continue

            result["mcp_servers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing Codex config."""
        from agent_sync.merge import deep_merge, merge_mcp_config
        from agent_sync.state import get_client_state

        # Get managed servers from state
        client_state = get_client_state(self.name)
        managed_servers = set(client_state.managed_servers.keys()) if client_state else set()

        # Merge MCP servers
        merged = merge_mcp_config(
            existing=existing,
            generated=generated,
            mcp_key="mcp_servers",
            client_name=self.name,
            managed_servers=managed_servers,
        )

        # Deep merge other top-level keys
        for key, value in generated.items():
            if key != "mcp_servers" and key in merged:
                if isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            elif key != "mcp_servers":
                merged[key] = value

        return merged

    def validate_support(self, registry: Registry) -> list[str]:
        """Validate that the registry is compatible with Codex."""
        warnings = []

        for server_name, server_def in registry.servers.items():
            # Check for unsupported transports
            if server_def.transport == TransportType.SSE:
                warnings.append(
                    f"Server '{server_name}' uses SSE transport which is not supported by Codex"
                )
            elif server_def.transport == TransportType.WS:
                warnings.append(
                    f"Server '{server_name}' uses WebSocket transport which is not supported by Codex"
                )

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the Codex configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert dict to TOML
        try:
            # Load existing config to preserve comments and structure
            if path.exists():
                with open(path, "r") as f:
                    doc = tomlkit.load(f)
            else:
                doc = tomlkit.document()

            # Update mcp_servers section
            if "mcp_servers" in config:
                if "mcp_servers" not in doc:
                    doc.add("mcp_servers", tomlkit.table())
                
                mcp_servers_table = doc["mcp_servers"]
                if not isinstance(mcp_servers_table, Table):
                    doc["mcp_servers"] = tomlkit.table()
                    mcp_servers_table = doc["mcp_servers"]

                # Clear existing managed servers
                # (This is a simplification - in production we'd be more careful)
                for key in list(mcp_servers_table.keys()):
                    del mcp_servers_table[key]

                # Add new servers
                for server_name, server_config in config["mcp_servers"].items():
                    mcp_servers_table[server_name] = server_config

            # Write atomically
            content = tomlkit.dumps(doc)
            write_atomically(path, content, validate=False)

        except Exception as e:
            raise AdapterError(f"Failed to write Codex config: {e}", self.name) from e
