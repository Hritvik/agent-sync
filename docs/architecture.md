# mcp-sync Architecture

## Overview

`mcp-sync` is a universal MCP configuration manager that provides a canonical registry for MCP servers and automatically generates or updates client-specific configurations through adapters.

## Core Principles

1. **One canonical source of truth** - The canonical registry in `servers.yaml` is the authoritative definition
2. **Client configs are generated outputs** - Client configuration files are derived from the canonical registry
3. **Never overwrite unrelated settings** - Merge logic preserves non-MCP settings and unmanaged servers
4. **Never silently resolve conflicts** - Conflicts are detected and reported rather than automatically overwritten
5. **Never expose secrets** - Secret values are redacted from logs, diffs, and diagnostics
6. **Prefer deterministic transformations** - Same input always produces the same output
7. **Keep adapters isolated** - Each client adapter is self-contained and independent
8. **Verify from official docs** - All client schemas are based on current official documentation
9. **Make every mutation previewable** - Dry-run mode shows exactly what will change
10. **No daemon required** - Tool runs on-demand with no background service

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Interface                          │
│                           (CLI)                                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Command Layer                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │   init   │ │  list    │ │  apply   │ │  diff    │ │ ...  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘ │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Core Logic Layer                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ │
│  │   Registry   │ │    Merge     │ │   Backup     │ │ State  │ │
│  │   Loading    │ │    Logic     │ │   & Write    │ │Tracking│ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  Validation  │ │  Redaction   │ │   Profile    │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Adapter Layer                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │  Codex   │ │  Claude  │ │  Cursor  │ │ VS Code  │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Client Configurations                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │config.toml│ │.claude.json│ │mcp.json │ │mcp.json │          │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Models (`models.py`)

Pydantic models define the canonical schema:

- **TransportType**: Enum for supported transports (stdio, http, sse, ws)
- **ServerConfig**: Union type for different server configurations
- **ServerDefinition**: Complete server definition with metadata and client filters
- **Registry**: Top-level container for all server definitions
- **Profiles**: Profile definitions for server groupings
- **State**: State tracking for managed servers across clients

### 2. Registry (`registry.py`)

Handles loading, validation, and filtering of the canonical registry:

- `load_registry()`: Load and validate `servers.yaml`
- `load_profiles()`: Load profile definitions
- `filter_servers_by_profile()`: Filter servers by profile
- `filter_servers_by_client()`: Filter servers by client inclusion/exclusion

### 3. Adapters (`adapters/`)

Each adapter implements the `ClientAdapter` protocol:

```python
class ClientAdapter(Protocol):
    name: str
    
    def detect(self) -> bool
    def config_path(self, scope: str) -> Path
    def load_config(self, scope: str) -> dict
    def render_servers(self, registry: Registry, scope: str) -> dict
    def merge_config(self, existing: dict, generated: dict, scope: str) -> dict
    def validate_support(self, registry: Registry) -> list[str]
    def write_config(self, config: dict, scope: str) -> None
```

**Key responsibilities:**
- Detect if client is installed
- Load existing client configuration
- Convert canonical servers to client-specific format
- Merge generated config with existing config
- Validate that registry features are supported
- Write configuration atomically

### 4. Merge Logic (`merge.py`)

Handles intelligent merging of configurations:

- `deep_merge()`: Deep merge two dictionaries
- `merge_mcp_config()`: Merge MCP servers while preserving non-MCP settings
- `detect_conflicts()`: Detect conflicts between existing and generated configs
- `configs_are_equal()`: Check if two configurations are equal

**Merge behavior:**
1. Preserve unmanaged servers from existing config
2. Update managed servers from generated config
3. Detect conflicts for unmanaged servers with different settings
4. Remove managed servers deleted from registry
5. Preserve non-MCP settings

### 5. Backup (`backup.py`)

Safe backup and atomic write operations:

- `create_backup()`: Create timestamped backup
- `list_backups()`: List available backups
- `restore_backup()`: Restore from backup
- `write_atomically()`: Write file atomically with validation
- `cleanup_old_backups()`: Remove old backups (keeps N most recent)

### 6. State Tracking (`state.py`)

Tracks which servers are managed by mcp-sync:

- `load_state()`: Load state from JSON
- `save_state()`: Save state to JSON
- `update_client_state()`: Update state for a client
- `is_server_managed()`: Check if a server is managed
- `remove_server_from_state()`: Remove server from state
- `clear_client_state()`: Clear all state for a client

**State structure:**
```json
{
  "clients": {
    "codex": {
      "config_path": "/path/to/config.toml",
      "managed_servers": {
        "server-name": "config-hash"
      },
      "last_applied": "2026-08-04T08:30:00Z",
      "mcp_sync_version": "0.1.0"
    }
  }
}
```

### 7. Redaction (`redaction.py`)

Secret handling and redaction:

- `looks_like_secret()`: Check if key name suggests a secret
- `looks_like_secret_value()`: Check if value looks like a secret
- `redact_value()`: Redact a value if it appears to be a secret
- `redact_dict()`: Redact secrets in a dictionary
- `check_env_vars_exist()`: Check which environment variables are missing
- `extract_env_references()`: Extract all environment variable references
- `warn_about_secrets()`: Generate warnings about potential secrets

### 8. CLI (`cli.py`)

Typer-based command-line interface:

Commands:
- `init`: Initialize configuration files
- `list`: Show canonical MCP servers
- `show`: Show details for a specific server
- `clients`: Show detected clients
- `validate`: Validate the canonical registry
- `diff`: Show planned changes without writing
- `apply`: Apply changes to client configurations
- `doctor`: Check configuration and environment
- `remove`: Remove a managed server
- `backup list`: List available backups
- `backup restore`: Restore from backup

### 9. Paths (`paths.py`)

Configuration file path utilities:

- `get_config_dir()`: Get mcp-sync configuration directory
- `get_servers_path()`: Get path to servers.yaml
- `get_profiles_path()`: Get path to profiles.yaml
- `get_state_path()`: Get path to state.json
- `get_backups_dir()`: Get path to backups directory
- `ensure_config_dirs()`: Ensure all directories exist

### 10. Exceptions (`exceptions.py`)

Custom exception hierarchy:

- `McpSyncError`: Base exception
- `ValidationError`: Configuration validation errors
- `ConflictError`: Configuration conflicts
- `AdapterError`: Adapter-specific errors
- `BackupError`: Backup operation errors
- `ConfigNotFoundError`: Configuration file not found
- `UnsupportedFeatureError`: Unsupported client features

## Data Flow

### Apply Operation Flow

```
1. Load canonical registry (servers.yaml)
2. Apply profile filter if specified
3. For each client:
   a. Check if client is detected
   b. Validate registry support (check for unsupported features)
   c. Load existing client configuration
   d. Render canonical servers to client-specific format
   e. Detect conflicts between existing and generated config
   f. If conflicts exist, report and skip (or handle based on policy)
   g. Merge generated config with existing config
   h. Create backup of existing config
   i. Write merged config atomically
   j. Update state tracking
4. Report results
```

### Merge Decision Tree

```
For each server in generated config:
  ├─ Server exists in existing config?
  │  ├─ Yes
  │  │  ├─ Is server managed by mcp-sync?
  │  │  │  ├─ Yes → Update with generated config
  │  │  │  └─ No → Check for conflict
  │  │  │     ├─ Configs identical → No action
  │  │  │     └─ Configs differ → Conflict error
  │  │  └─
  │  └─ No → Add to merged config
  └─
For each server in existing config:
  ├─ Is server managed by mcp-sync?
  │  ├─ Yes
  │  │  ├─ Server in generated config?
  │  │  │  ├─ Yes → Already handled above
  │  │  │  └─ No → Remove from merged config (deleted from registry)
  │  │  └─
  │  └─ No → Preserve in merged config (unmanaged)
  └─
```

## Configuration Locations

### mcp-sync Configuration
- **Config directory:** `~/.config/mcp-sync/`
- **Servers:** `~/.config/mcp-sync/servers.yaml`
- **Profiles:** `~/.config/mcp-sync/profiles.yaml`
- **State:** `~/.config/mcp-sync/state.json`
- **Backups:** `~/.config/mcp-sync/backups/<client>/`

### Client Configurations
- **Codex:** `~/.codex/config.toml` (user), `.codex/config.toml` (project)
- **Claude Code:** `~/.claude.json` (user/local), `.mcp.json` (project)
- **Cursor:** `~/.cursor/mcp.json` (global), `.cursor/mcp.json` (project)
- **VS Code:** User profile `mcp.json` (user), `.vscode/mcp.json` (workspace)

## Security Considerations

1. **Secret handling:**
   - Never write resolved secret values to generated configs
   - Prefer environment variable references
   - Redact secrets from logs, diffs, and diagnostics
   - Warn about potential secrets in configuration

2. **File permissions:**
   - Preserve existing file permissions when writing
   - Avoid following unsafe symlinks
   - Use atomic writes to prevent partial writes

3. **Validation:**
   - Validate canonical registry before applying
   - Parse generated content before replacing original
   - Check for missing environment variables

4. **Backups:**
   - Always create backups before modifications
   - Store backups with timestamps
   - Support backup restoration
   - Clean up old backups

## Extensibility

### Adding a New Client

To add support for a new MCP client:

1. Research the client's MCP configuration format from official documentation
2. Create a新的 adapter class inheriting from `BaseAdapter`
3. Implement all required methods from the `ClientAdapter` protocol
4. Add the adapter to the `ADAPTERS` dict in `cli.py`
5. Add tests for the new adapter

See `docs/adding-an-adapter.md` for detailed guidance.

### Adding a New Transport

To add support for a new transport type:

1. Add the transport to the `TransportType` enum in `models.py`
2. Create a new config model (e.g., `NewTransportServerConfig`)
3. Add the new config to the `ServerConfig` union type
4. Update each adapter to handle the new transport type
5. Add validation in `validate_support()` methods

## Testing Strategy

### Unit Tests
- Model validation
- Registry loading and filtering
- Profile resolution
- Secret detection and redaction
- Path expansion
- State file behavior

### Adapter Tests
- Empty configuration
- Existing unrelated settings
- Manually configured MCP servers
- Previously managed MCP servers
- Malformed configuration
- Comments (where supported)
- Duplicate server names
- Local and remote server configurations

### Safety Tests
- No secrets in logs
- Backups are created
- Writes are atomic
- Unrelated settings survive
- Dry-run makes no changes
- Conflicts don't overwrite data
- Failed parse leaves original untouched

### CLI Tests
- All commands with temporary directories
- Environment variable or dependency injection for config locations
- Error handling and exit codes

## Performance Considerations

- Configuration files are typically small (< 10KB)
- No network calls by default
- State tracking is in-memory during operation
- Atomic writes prevent corruption
- Backup cleanup limits disk usage

## Error Handling

### Exit Codes
- `0`: Success
- `1`: Validation error
- `2`: Conflict
- `3`: Unsupported client capability
- `4`: Filesystem error
- `5`: Partial application

### Error Messages
- Clear and actionable
- Include file paths when relevant
- Suggest corrections when possible
- Never include secret values

## Future Enhancements

Potential future features (not in scope for v1):

- Import command for existing client configurations
- `mcp-sync add` command for adding servers from CLI
- Automatic command availability checking
- Network connectivity checks for remote servers
- Windows support improvements
- GUI for configuration management
- Cloud synchronization
- Organization-wide policy management
