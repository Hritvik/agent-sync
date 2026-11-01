"""Antigravity (Google) MCP client adapter."""

import json
from pathlib import Path
from typing import Any

from agent_sync.adapters.base import BaseAdapter
from agent_sync.backup import write_atomically
from agent_sync.exceptions import AdapterError
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


class AntigravityAdapter(BaseAdapter):
    """Adapter for Antigravity (Google) MCP configuration."""

    name = "antigravity"

    def detect(self) -> bool:
        """Check if Antigravity appears to be installed."""
        # Check for Antigravity config directory
        config_path = Path.home() / ".gemini" / "antigravity"
        return config_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for Antigravity."""
        if scope == "user":
            return Path.home() / ".gemini" / "antigravity" / "mcp_config.json"
        elif scope == "project":
            return Path.cwd() / ".agent" / "mcp_config.json"
        else:
            raise AdapterError(f"Unsupported scope for Antigravity: {scope}", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the Antigravity configuration."""
        path = self.config_path(scope)

        if not path.exists():
            # Return empty config if file doesn't exist
            return {}

        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return {}
            
            return data
        except json.JSONDecodeError as e:
            raise AdapterError(f"Failed to parse Antigravity config: {e}", self.name) from e
        except Exception as e:
            raise AdapterError(f"Failed to load Antigravity config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to Antigravity-specific JSON format."""
        result: dict[str, Any] = {"mcpServers": {}}

        for server_name, server_def in registry.servers.items():
            if not server_def.enabled:
                continue

            server_config: dict[str, Any] = {}

            # Handle different transport types
            if isinstance(server_def.config, StdioServerConfig):
                server_config["command"] = server_def.config.command
                if server_def.config.args:
                    server_config["args"] = server_def.config.args
                
                # Handle environment variables
                # IMPORTANT: Antigravity does NOT support environment variable interpolation
                # All values must be literal strings
                if server_def.config.env:
                    env_dict = {}
                    for key, value in server_def.config.env.items():
                        if isinstance(value, EnvValueLiteral):
                            env_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            # Antigravity doesn't support ${VAR} syntax
                            # We'll use the variable name as a placeholder
                            # The user will need to set these manually
                            env_dict[key] = f"REPLACE_WITH_{value.from_env}"
                    
                    if env_dict:
                        server_config["env"] = env_dict

            elif isinstance(server_def.config, HttpServerConfig):
                server_config["type"] = "http"
                server_config["url"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    headers_dict = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueLiteral):
                            headers_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            # Antigravity doesn't support ${VAR} syntax
                            headers_dict[key] = f"REPLACE_WITH_{value.from_env}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            elif isinstance(server_def.config, SseServerConfig):
                server_config["type"] = "sse"
                server_config["url"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    headers_dict = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueLiteral):
                            headers_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            headers_dict[key] = f"REPLACE_WITH_{value.from_env}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            else:
                # WebSocket is not supported by Antigravity
                continue

            result["mcpServers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing Antigravity config."""
        from agent_sync.merge import deep_merge, merge_mcp_config
        from agent_sync.state import get_client_state

        # Get managed servers from state
        client_state = get_client_state(self.name)
        managed_servers = set(client_state.managed_servers.keys()) if client_state else set()

        # Merge MCP servers
        merged = merge_mcp_config(
            existing=existing,
            generated=generated,
            mcp_key="mcpServers",
            client_name=self.name,
            managed_servers=managed_servers,
        )

        # Deep merge other top-level keys
        for key, value in generated.items():
            if key != "mcpServers" and key in merged:
                if isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            elif key != "mcpServers":
                merged[key] = value

        return merged

    def validate_support(self, registry: Registry) -> list[str]:
        """Validate that the registry is compatible with Antigravity."""
        warnings = []

        for server_name, server_def in registry.servers.items():
            # Check for unsupported transports
            if server_def.transport == TransportType.WS:
                warnings.append(
                    f"Server '{server_name}' uses WebSocket transport which is not supported by Antigravity"
                )

            # Warn about environment variable references
            # Antigravity doesn't support ${VAR} interpolation
            def check_for_env_refs(config: Any) -> list[str]:
                refs = []
                if isinstance(config, dict):
                    for key, value in config.items():
                        if isinstance(value, EnvValueSource):
                            refs.append(f"{key}: {value.from_env}")
                        elif isinstance(value, dict):
                            refs.extend(check_for_env_refs(value))
                return refs

            env_refs = check_for_env_refs(server_def.config)
            if env_refs:
                warnings.append(
                    f"Server '{server_name}' uses environment variable references ({', '.join(env_refs)}) "
                    "but Antigravity does not support ${VAR} interpolation. "
                    "These will be replaced with placeholder values."
                )

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the Antigravity configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON
        try:
            content = json.dumps(config, indent=2)
            write_atomically(path, content, validate=True)
        except Exception as e:
            raise AdapterError(f"Failed to write Antigravity config: {e}", self.name) from e
