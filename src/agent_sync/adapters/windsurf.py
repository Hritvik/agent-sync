"""Windsurf (Codeium Cascade) MCP client adapter."""

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


class WindsurfAdapter(BaseAdapter):
    """Adapter for Windsurf (Codeium Cascade) MCP configuration."""

    name = "windsurf"

    def detect(self) -> bool:
        """Check if Windsurf appears to be installed."""
        # Check for Windsurf config directory
        config_path = Path.home() / ".codeium" / "windsurf"
        return config_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for Windsurf."""
        if scope == "user":
            return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"
        else:
            # Windsurf only supports global config, no project-level
            raise AdapterError(f"Windsurf only supports global configuration, not '{scope}' scope", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the Windsurf configuration."""
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
            raise AdapterError(f"Failed to parse Windsurf config: {e}", self.name) from e
        except Exception as e:
            raise AdapterError(f"Failed to load Windsurf config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to Windsurf-specific JSON format."""
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
                if server_def.config.env:
                    env_dict = {}
                    for key, value in server_def.config.env.items():
                        if isinstance(value, EnvValueLiteral):
                            env_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            # Windsurf uses ${env:VAR} syntax
                            env_dict[key] = f"${{env:{value.from_env}}}"
                    
                    if env_dict:
                        server_config["env"] = env_dict

            elif isinstance(server_def.config, HttpServerConfig):
                # Windsurf uses serverUrl instead of url for remote servers
                server_config["serverUrl"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    headers_dict = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueLiteral):
                            headers_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            headers_dict[key] = f"${{env:{value.from_env}}}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            elif isinstance(server_def.config, SseServerConfig):
                # Windsurf uses serverUrl for SSE as well
                server_config["serverUrl"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    headers_dict = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueLiteral):
                            headers_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            headers_dict[key] = f"${{env:{value.from_env}}}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            else:
                # WebSocket is not supported by Windsurf
                continue

            result["mcpServers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing Windsurf config."""
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
        """Validate that the registry is compatible with Windsurf."""
        warnings = []

        for server_name, server_def in registry.servers.items():
            # Check for unsupported transports
            if server_def.transport == TransportType.WS:
                warnings.append(
                    f"Server '{server_name}' uses WebSocket transport which is not supported by Windsurf"
                )

        # Warn about 100 tool limit
        # This is a soft warning since we can't count tools without running servers
        warnings.append(
            "Windsurf has a hard limit of 100 tools across all MCP servers. "
            "If your servers collectively expose more than 100 tools, some will be unavailable."
        )

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the Windsurf configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON
        try:
            content = json.dumps(config, indent=2)
            write_atomically(path, content, validate=True)
        except Exception as e:
            raise AdapterError(f"Failed to write Windsurf config: {e}", self.name) from e
