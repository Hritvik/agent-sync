"""VS Code (GitHub Copilot) MCP client adapter."""

import json
from pathlib import Path
from typing import Any

from agent_sync.adapters.base import BaseAdapter
from agent_sync.backup import compute_config_hash, write_atomically
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
from agent_sync.redaction import redact_dict


class VSCodeAdapter(BaseAdapter):
    """Adapter for VS Code (GitHub Copilot) MCP configuration."""

    name = "vscode"

    def detect(self) -> bool:
        """Check if VS Code appears to be installed."""
        # Check for VS Code config directory
        config_path = Path.home() / ".vscode"
        # Also check for common VS Code locations
        app_path = Path("/Applications/Visual Studio Code.app")
        return config_path.exists() or app_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for VS Code."""
        if scope == "user":
            # User profile location - this is platform-specific
            # For simplicity, we'll use a common location
            # In production, this should be determined based on OS
            return Path.home() / ".vscode" / "mcp.json"
        elif scope == "project":
            return Path.cwd() / ".vscode" / "mcp.json"
        else:
            raise AdapterError(f"Unsupported scope for VS Code: {scope}", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the VS Code configuration."""
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
            raise AdapterError(f"Failed to parse VS Code config: {e}", self.name) from e
        except Exception as e:
            raise AdapterError(f"Failed to load VS Code config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to VS Code-specific JSON format."""
        result: dict[str, Any] = {"servers": {}}

        for server_name, server_def in registry.servers.items():
            if not server_def.enabled:
                continue

            server_config: dict[str, Any] = {}

            # Handle different transport types
            if isinstance(server_def.config, StdioServerConfig):
                server_config["type"] = "stdio"
                server_config["command"] = server_def.config.command
                if server_def.config.args:
                    server_config["args"] = server_def.config.args
                if server_def.config.cwd:
                    server_config["cwd"] = server_def.config.cwd
                
                # Handle environment variables
                if server_def.config.env:
                    env_dict = {}
                    for key, value in server_def.config.env.items():
                        if isinstance(value, EnvValueLiteral):
                            env_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            # VS Code uses input variables for sensitive data
                            # For now, we'll use the variable name as a placeholder
                            # In a full implementation, we'd create input variable definitions
                            env_dict[key] = f"${{input:{value.from_env}}}"
                    
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
                            headers_dict[key] = f"${{input:{value.from_env}}}"
                    
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
                            headers_dict[key] = f"${{input:{value.from_env}}}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            else:
                # WebSocket is not supported by VS Code
                continue

            result["servers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing VS Code config."""
        from agent_sync.merge import deep_merge, merge_mcp_config
        from agent_sync.state import get_client_state

        # Get managed servers from state
        client_state = get_client_state(self.name)
        managed_servers = set(client_state.managed_servers.keys()) if client_state else set()

        # Merge MCP servers (note: VS Code uses "servers" not "mcpServers")
        merged = merge_mcp_config(
            existing=existing,
            generated=generated,
            mcp_key="servers",
            client_name=self.name,
            managed_servers=managed_servers,
        )

        # Deep merge other top-level keys (like "inputs", "sandbox")
        for key, value in generated.items():
            if key != "servers" and key in merged:
                if isinstance(merged[key], dict) and isinstance(value, dict):
                    merged[key] = deep_merge(merged[key], value)
                else:
                    merged[key] = value
            elif key != "servers":
                merged[key] = value

        return merged

    def validate_support(self, registry: Registry) -> list[str]:
        """Validate that the registry is compatible with VS Code."""
        warnings = []

        for server_name, server_def in registry.servers.items():
            # Check for unsupported transports
            if server_def.transport == TransportType.WS:
                warnings.append(
                    f"Server '{server_name}' uses WebSocket transport which is not supported by VS Code"
                )

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the VS Code configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON
        try:
            content = json.dumps(config, indent=2)
            write_atomically(path, content, validate=True)
        except Exception as e:
            raise AdapterError(f"Failed to write VS Code config: {e}", self.name) from e
