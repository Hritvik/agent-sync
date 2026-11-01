# Adding a New Adapter

This guide explains how to add support for a new MCP client to mcp-sync.

## Overview

Each MCP client adapter is responsible for:
- Detecting if the client is installed
- Loading the client's existing configuration
- Converting canonical server definitions to the client's format
- Merging generated configuration with existing configuration
- Writing the final configuration atomically
- Validating that the registry's features are supported by the client

## Step 1: Research the Client

Before implementing an adapter, research the client's MCP configuration format from official documentation:

1. **Configuration location:** Where does the client store its MCP config?
2. **File format:** JSON, TOML, YAML, or another format?
3. **Schema:** What is the structure of the MCP configuration?
4. **Scope support:** Does it support user-level and project-level configuration?
5. **Transports:** Which MCP transports does it support (stdio, http, sse, ws)?
6. **Environment variables:** How does it handle environment variable references?
7. **Comments:** Does it preserve comments in the configuration file?
8. **Restart required:** Does the client need to be restarted after config changes?

Document your findings in `docs/client-compatibility.md` with the date verified.

## Step 2: Create the Adapter File

Create a new file in `src/mcp_sync/adapters/` named after the client (e.g., `newclient.py`).

## Step 3: Implement the Adapter

Your adapter should inherit from `BaseAdapter` and implement all required methods:

```python
from pathlib import Path
from typing import Any

from mcp_sync.adapters.base import BaseAdapter
from mcp_sync.backup import write_atomically
from mcp_sync.exceptions import AdapterError
from mcp_sync.models import (
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


class NewClientAdapter(BaseAdapter):
    """Adapter for NewClient MCP configuration."""

    name = "newclient"

    def detect(self) -> bool:
        """Check if NewClient appears to be installed."""
        # Check for client-specific indicators
        # Examples: config directory, executable, etc.
        config_path = Path.home() / ".newclient"
        return config_path.exists()

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for NewClient."""
        if scope == "user":
            return Path.home() / ".newclient" / "config.json"
        elif scope == "project":
            return Path.cwd() / ".newclient" / "config.json"
        else:
            raise AdapterError(f"Unsupported scope for NewClient: {scope}", self.name)

    def load_config(self, scope: str = "user") -> dict:
        """Load and parse the NewClient configuration."""
        path = self.config_path(scope)

        if not path.exists():
            return {}

        try:
            # Load the configuration file
            # Use appropriate parser for the file format
            import json
            with open(path, "r") as f:
                data = json.load(f)
            
            if not isinstance(data, dict):
                return {}
            
            return data
        except Exception as e:
            raise AdapterError(f"Failed to load NewClient config: {e}", self.name) from e

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to NewClient-specific format."""
        result: dict[str, Any] = {"mcpServers": {}}  # Adjust key as needed

        for server_name, server_def in registry.servers.items():
            if not server_def.enabled:
                continue

            server_config: dict[str, Any] = {}

            # Handle different transport types
            if isinstance(server_def.config, StdioServerConfig):
                # Convert stdio config to client format
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
                            # Convert to client-specific env var syntax
                            env_dict[key] = f"${{{value.from_env}}}"
                    
                    if env_dict:
                        server_config["env"] = env_dict

            elif isinstance(server_def.config, HttpServerConfig):
                # Convert HTTP config to client format
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

            # Handle other transport types as needed
            elif isinstance(server_def.config, SseServerConfig):
                # Convert SSE config
                pass

            elif isinstance(server_def.config, WsServerConfig):
                # Convert WebSocket config
                pass

            result["mcpServers"][server_name] = server_config

        return result

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge generated MCP config with existing NewClient config."""
        from mcp_sync.merge import deep_merge, merge_mcp_config
        from mcp_sync.state import get_client_state

        # Get managed servers from state
        client_state = get_client_state(self.name)
        managed_servers = set(client_state.managed_servers.keys()) if client_state else set()

        # Merge MCP servers (adjust mcp_key as needed)
        merged = merge_mcp_config(
            existing=existing,
            generated=generated,
            mcp_key="mcpServers",  # Adjust to client's key
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
        """Validate that the registry is compatible with NewClient."""
        warnings = []

        for server_name, server_def in registry.servers.items():
            # Check for unsupported transports
            if server_def.transport == TransportType.WS:
                warnings.append(
                    f"Server '{server_name}' uses WebSocket transport which is not supported by NewClient"
                )

        return warnings

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Write the NewClient configuration atomically."""
        path = self.config_path(scope)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to client's format
        try:
            import json
            content = json.dumps(config, indent=2)
            write_atomically(path, content, validate=True)
        except Exception as e:
            raise AdapterError(f"Failed to write NewClient config: {e}", self.name) from e
```

## Step 4: Register the Adapter

Add your adapter to the `ADAPTERS` dictionary in `src/mcp_sync/cli.py`:

```python
from mcp_sync.adapters.newclient import NewClientAdapter

ADAPTERS = {
    "codex": CodexAdapter(),
    "claude": ClaudeAdapter(),
    "cursor": CursorAdapter(),
    "vscode": VSCodeAdapter(),
    "newclient": NewClientAdapter(),  # Add your adapter here
}
```

## Step 5: Handle Client-Specific Details

### Configuration Key

Different clients use different keys for MCP servers:
- Codex: `mcp_servers` (TOML table)
- Claude Code: `mcpServers` (JSON object)
- Cursor: `mcpServers` (JSON object)
- VS Code: `servers` (JSON object)

Update the `mcp_key` parameter in `merge_config()` and `detect_conflicts()` calls accordingly.

### Environment Variable Syntax

Different clients use different syntax for environment variable references:
- Codex: `env_vars = ["VAR_NAME"]` or `env_vars = [{ name = "VAR_NAME", source = "local" }]`
- Claude Code: `${VAR}` or direct values
- Cursor: `${env:VAR}`
- VS Code: `${input:var-id}` for sensitive data

Update the `render_servers()` method to use the correct syntax.

### Transport Support

Check which transports the client supports and update `validate_support()` accordingly:
- Codex: stdio, http
- Claude Code: stdio, http, sse, ws
- Cursor: stdio, http, sse
- VS Code: stdio, http, sse

### File Format

Use the appropriate library for the client's file format:
- JSON: Python standard library `json`
- TOML: `tomlkit` (preserves comments)
- YAML: `PyYAML` or `ruamel.yaml`

## Step 6: Create Tests

Create test files in `tests/adapters/`:

### Test Structure

```python
import pytest
from pathlib import Path
from mcp_sync.adapters.newclient import NewClientAdapter
from mcp_sync.models import Registry, StdioServerConfig, EnvValueLiteral


def test_newclient_detect():
    """Test client detection."""
    adapter = NewClientAdapter()
    # Test with client installed
    # Test with client not installed


def test_newclient_config_path():
    """Test configuration path resolution."""
    adapter = NewClientAdapter()
    user_path = adapter.config_path("user")
    project_path = adapter.config_path("project")
    # Assert paths are correct


def test_newclient_load_config():
    """Test loading existing configuration."""
    adapter = NewClientAdapter()
    # Test with empty config
    # Test with existing config
    # Test with malformed config


def test_newclient_render_servers():
    """Test rendering canonical servers to client format."""
    adapter = NewClientAdapter()
    
    registry = Registry(
        version=1,
        servers={
            "test-server": ServerDefinition(
                description="Test server",
                transport=TransportType.STDIO,
                config=StdioServerConfig(
                    command="test",
                    args=["--arg"],
                ),
                enabled=True,
            )
        }
    )
    
    generated = adapter.render_servers(registry)
    # Assert generated config has correct structure


def test_newclient_merge_config():
    """Test merging generated config with existing config."""
    adapter = NewClientAdapter()
    # Test with empty existing config
    # Test with existing unrelated settings
    # Test with existing unmanaged servers
    # Test with existing managed servers


def test_newclient_validate_support():
    """Test validation of registry support."""
    adapter = NewClientAdapter()
    # Test with supported transports
    # Test with unsupported transports


def test_newclient_write_config():
    """Test writing configuration."""
    adapter = NewClientAdapter()
    # Test with temporary directory
    # Test atomic write
    # Test file creation
```

### Fixture Files

Create fixture files in `tests/fixtures/adapters/newclient/`:
- `empty.json` - Empty configuration
- `existing.json` - Configuration with existing settings
- `malformed.json` - Invalid JSON for error handling
- `with-unmanaged.json` - Configuration with unmanaged MCP servers
- `with-managed.json` - Configuration with managed MCP servers

## Step 7: Update Documentation

Update the following files:

1. **`docs/client-compatibility.md`** - Add your research findings
2. **`docs/architecture.md`** - Add your client to the architecture diagram
3. **`README.md`** - Add your client to the supported clients list

## Step 8: Test Manually

Before committing, test manually:

```bash
# Initialize config
mcp-sync init

# Add a test server to servers.yaml
# Edit ~/.config/mcp-sync/servers.yaml

# Validate
mcp-sync validate

# Check diff
mcp-sync diff --client newclient

# Apply (dry-run)
mcp-sync apply --client newclient --dry-run

# Apply for real
mcp-sync apply --client newclient

# Verify the client's config file
# Check that the client recognizes the MCP servers
```

## Common Patterns

### TOML with Comments (Codex)

For clients that use TOML and preserve comments:

```python
import tomlkit
from tomlkit.items import Table

def write_config(self, config: dict, scope: str = "user") -> None:
    path = self.config_path(scope)
    
    if path.exists():
        with open(path, "r") as f:
            doc = tomlkit.load(f)
    else:
        doc = tomlkit.document()
    
    # Update specific section while preserving structure
    if "mcp_servers" in config:
        if "mcp_servers" not in doc:
            doc.add("mcp_servers", tomlkit.table())
        
        mcp_servers_table = doc["mcp_servers"]
        for key in list(mcp_servers_table.keys()):
            del mcp_servers_table[key]
        
        for server_name, server_config in config["mcp_servers"].items():
            mcp_servers_table[server_name] = server_config
    
    content = tomlkit.dumps(doc)
    write_atomically(path, content, validate=False)
```

### JSON with Schema Validation

For clients that use JSON:

```python
import json

def write_config(self, config: dict, scope: str = "user") -> None:
    path = self.config_path(scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    content = json.dumps(config, indent=2)
    write_atomically(path, content, validate=True)
```

### Multiple Configuration Files

Some clients have multiple config files (user, project, local). Handle this in `config_path()` and `load_config()`:

```python
def config_path(self, scope: str = "user") -> Path:
    if scope == "user":
        return Path.home() / ".client" / "config.json"
    elif scope == "project":
        return Path.cwd() / ".client" / "config.json"
    elif scope == "local":
        # Local scope might be in user config under project path
        return Path.home() / ".client" / "projects" / Path.cwd().name / "config.json"
    else:
        raise AdapterError(f"Unsupported scope: {scope}", self.name)
```

## Troubleshooting

### Configuration Not Loading

- Check the file path is correct
- Verify the file format parser matches the actual format
- Add error handling for malformed files

### Merge Not Working

- Verify the `mcp_key` parameter matches the client's actual key
- Check that state tracking is working correctly
- Ensure managed servers are being tracked

### Client Not Recognizing Changes

- Check if the client needs to be restarted
- Verify the configuration file format is correct
- Test the generated config manually with the client

### Transport Not Supported

This is expected behavior. The adapter will:
1. Skip servers with unsupported transports in `render_servers()`
2. Generate warnings in `validate_support()`
3. Report warnings during `diff` and `apply`

## Best Practices

1. **Keep adapters isolated** - Don't share logic between adapters unless it's in the core layer
2. **Use the merge utilities** - Leverage `merge_mcp_config()` and `deep_merge()` from the core
3. **Validate early** - Validate support before attempting to render or merge
4. **Handle errors gracefully** - Use `AdapterError` for adapter-specific errors
5. **Test edge cases** - Empty configs, malformed configs, missing files
6. **Document client-specific behavior** - Note any quirks in the adapter docstring
7. **Follow the protocol** - Implement all methods from `ClientAdapter` protocol
