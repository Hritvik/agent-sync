"""Claude Code (Anthropic) MCP client adapter."""

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


class ClaudeAdapter(BaseAdapter):
    """Adapter for Claude Code (Anthropic) MCP configuration."""

    name = "claude"

    def detect(self) -> bool:
        """Check if Claude Code appears to be installed."""
        # Check for Claude config file
        config_path = Path.home() / ".claude.json"
        return config_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for Claude Code."""
        if scope == "user":
            return Path.home() / ".claude.json"
        elif scope == "project":
            return Path.cwd() / ".mcp.json"
        elif scope == "local":
            # Local scope is stored in ~/.claude.json under project path
            # For simplicity, we use the same file as user scope
            return Path.home() / ".claude.json"
        else:
            raise AdapterError(f"Unsupported scope for Claude Code: {scope}", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the Claude Code configuration."""
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
            raise AdapterError(f"Failed to parse Claude Code config: {e}", self.name) from e
        except Exception as e:
            raise AdapterError(f"Failed to load Claude Code config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to Claude Code-specific JSON format."""
        result: dict[str, Any] = {"mcpServers": {}}

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
                
                # Handle environment variables
                if server_def.config.env:
                    env_dict = {}
                    for key, value in server_def.config.env.items():
                        if isinstance(value, EnvValueLiteral):
                            env_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            # Claude Code uses direct variable references in env
                            # We'll use the variable name as the value for now
                            # In a full implementation, we might need to handle this differently
                            env_dict[key] = f"${{{value.from_env}}}"
                    
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
                            headers_dict[key] = f"${{{value.from_env}}}"
                    
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
                            headers_dict[key] = f"${{{value.from_env}}}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            elif isinstance(server_def.config, WsServerConfig):
                server_config["type"] = "ws"
                server_config["url"] = server_def.config.url
                
                # Handle headers
                if server_def.config.headers:
                    headers_dict = {}
                    for key, value in server_def.config.headers.items():
                        if isinstance(value, EnvValueLiteral):
                            headers_dict[key] = value.value
                        elif isinstance(value, EnvValueSource):
                            headers_dict[key] = f"${{{value.from_env}}}"
                    
                    if headers_dict:
                        server_config["headers"] = headers_dict

            result["mcpServers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing Claude Code config."""
        from agent_sync.merge import deep_merge, merge_mcp_config
        from agent_sync.state import get_client_state

        # Get managed servers from state
        client_state = get_client_state(self.name)
        managed_servers = set(client_state.managed_servers.keys()) if client_state else set()

        # For project scope, we need to handle the structure differently
        # Project scope stores servers directly in mcpServers
        # User/local scope stores them under project paths or top-level mcpServers
        
        if scope == "project":
            # Project scope is simpler - just the mcpServers object
            merged = merge_mcp_config(
                existing=existing,
                generated=generated,
                mcp_key="mcpServers",
                client_name=self.name,
                managed_servers=managed_servers,
            )
        else:
            # User/local scope - merge into the full config
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
        """Validate that the registry is compatible with Claude Code."""
        warnings = []

        # Claude Code supports all transports (stdio, http, sse, ws)
        # No warnings needed based on current research

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the Claude Code configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to JSON
        try:
            content = json.dumps(config, indent=2)
            write_atomically(path, content, validate=True)
        except Exception as e:
            raise AdapterError(f"Failed to write Claude Code config: {e}", self.name) from e
