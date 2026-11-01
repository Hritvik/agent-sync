# MCP Client Compatibility Matrix

**Last Updated:** August 4, 2026

This document documents the current MCP configuration formats for supported clients based on official documentation verified on this date.

## Overview

Each MCP-compatible client stores its configuration in different locations, formats, and schemas. This matrix captures the differences to inform adapter implementation.

---

## Codex (OpenAI)

### Configuration Path
- **User-level:** `~/.codex/config.toml`
- **Project-level:** `.codex/config.toml` (trusted projects only)

### Format
- **File format:** TOML
- **Schema reference:** https://developers.openai.com/codex/config-schema.json
- **IntelliSense:** Available with Even Better TOML extension by adding `#:schema https://developers.openai.com/codex/config-schema.json` to top of file

### Scope Support
- **User-level:** Yes - `~/.codex/config.toml`
- **Project-level:** Yes - `.codex/config.toml` (only when project is trusted)

### Supported Transports
- **stdio:** Yes
- **streamable-http:** Yes

### Configuration Schema

#### STDIO Servers
```toml
[mcp_servers.<server-name>]
command = "npx"  # required
args = ["-y", "@playwright/mcp@latest"]  # optional
env = { KEY = "value" }  # optional
env_vars = ["LOCAL_TOKEN", { name = "REMOTE_TOKEN", source = "remote" }]  # optional
cwd = "/path/to/dir"  # optional
experimental_environment = "remote"  # optional
startup_timeout_sec = 10  # optional, default: 10
tool_timeout_sec = 60  # optional, default: 60
enabled = true  # optional
required = false  # optional
enabled_tools = ["tool1", "tool2"]  # optional
disabled_tools = ["tool3"]  # optional
default_tools_approval_mode = "auto"  # optional: auto, prompt, writes, approve
```

#### HTTP Servers
```toml
[mcp_servers.<server-name>]
url = "https://mcp.example.com/mcp"  # required
auth = "oauth"  # optional: oauth (default), chatgpt
bearer_token_env_var = "API_TOKEN"  # optional
http_headers = { Authorization = "Bearer token" }  # optional
env_http_headers = { Authorization = "API_TOKEN" }  # optional
```

### Environment Variable Syntax
- **Static values:** `env = { KEY = "value" }`
- **From environment:** `env_vars = ["VAR_NAME"]` or `env_vars = [{ name = "VAR_NAME", source = "local" }]`
- **Remote environment:** `env_vars = [{ name = "VAR_NAME", source = "remote" }]` (requires remote MCP stdio)

### Configuration Sharing
- **Shared across CLI and IDE:** Yes - ChatGPT desktop app, Codex CLI, and IDE extension share the same `config.toml`

### Official CLI Commands
- **Add server:** `codex mcp add <name> -- <command> [args...]`
- **OAuth login:** `codex mcp login <server-name>`

### Comment Preservation
- **Preserves comments:** Yes (with Even Better TOML extension)

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented, but TOML format generally allows

### Restart Required
- **Restart required:** Yes

### Additional Notes
- Project-scoped config cannot override certain keys: `openai_base_url`, `chatgpt_base_url`, `apps_mcp_product_sku`, `model_provider`, `model_providers`, `notify`, `profile`, `profiles`, `experimental_realtime_ws_base_url`, `otel`
- Supports OAuth with configurable callback port: `mcp_oauth_callback_port` and `mcp_oauth_callback_url`
- JSON schema available at https://developers.openai.com/codex/config-schema.json

---

## Claude Code (Anthropic)

### Configuration Path
- **User scope:** `~/.claude.json` (under top-level `mcpServers` key for user-scoped, under project path for local-scoped)
- **Project scope:** `.mcp.json` in project root

### Format
- **File format:** JSON
- **Schema:** JSON with `mcpServers` top-level object

### Scope Support
Three distinct scopes:
- **Local:** Available only to you, only in current project. Stored in `~/.claude.json` under the project's path. Default when adding servers.
- **Project:** Shared with team via version control. Stored in `.mcp.json` in project root.
- **User:** Available to you in all projects. Stored in `~/.claude.json` under top-level `mcpServers` key.

### Supported Transports
- **stdio:** Yes
- **http:** Yes (also accepts alias `streamable-http`)
- **sse:** Yes
- **ws:** Yes (WebSocket)

### Configuration Schema

#### STDIO Servers
```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@playwright/mcp@latest"],
      "env": {
        "API_KEY": "value"
      }
    }
  }
}
```

#### HTTP/SSE Servers
```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

#### WebSocket Servers
```json
{
  "mcpServers": {
    "server-name": {
      "type": "ws",
      "url": "wss://mcp.example.com/socket",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

### Environment Variable Syntax
- **In env object:** Direct string values
- **Variable expansion:** `${VAR}` expansion in `command` and `args` for project-scoped `.mcp.json` requires default like `${CLAUDE_PROJECT_DIR:-.}`
- **Plugin-provided configs:** Substitute `${CLAUDE_PROJECT_DIR}` directly without default

### Configuration Sharing
- **Shared across CLI and IDE:** Not explicitly documented as shared

### Official CLI Commands
- **Add server:** `claude mcp add [options] <name> -- <command> [args...]`
- **Add HTTP server:** `claude mcp add --transport http <name> <url>`
- **Add SSE server:** `claude mcp add --transport sse <name> <url>`
- **Add from JSON:** `claude mcp add-json <name> '<json-string>'`
- **Scope selection:** `--scope local|project|user` (default: local)
- **Environment variables:** `--env KEY=value`
- **Headers:** `--header "Header: value"`

### Comment Preservation
- **Preserves comments:** JSON format does not support comments

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented

### Restart Required
- **Restart required:** Yes (new Claude Code session required after editing `.mcp.json`)

### Additional Notes
- Project-scoped servers require approval on first use (security measure)
- A JSON entry with `url` but no `type` is a configuration error
- Supports dynamic headers via `headersHelper` for custom authentication
- Supports OAuth with pre-configured credentials
- `CLAUDE_CONFIG_DIR` environment variable can override config directory location
- On Windows, `~/.claude.json` resolves to `%USERPROFILE%\.claude.json`

---

## Cursor

### Configuration Path
- **Global:** `~/.cursor/mcp.json` in home directory
- **Project-specific:** `.cursor/mcp.json` in project folder

### Format
- **File format:** JSON
- **Schema:** JSON with `mcpServers` top-level object

### Scope Support
- **Global:** Available across all Cursor projects
- **Project:** Available only in current repository, shared via version control
- **Merge behavior:** Both files are merged; project-level config takes priority when same server name appears in both

### Supported Transports
- **stdio:** Yes
- **http:** Yes
- **sse:** Yes

### Configuration Schema

#### STDIO Servers
```json
{
  "mcpServers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "mcp-server"],
      "env": {
        "API_KEY": "value"
      },
      "envFile": ".env"
    }
  }
}
```

#### HTTP/SSE Servers
```json
{
  "mcpServers": {
    "server-name": {
      "url": "http://localhost:3000/mcp",
      "headers": {
        "API_KEY": "value"
      }
    }
  }
}
```

#### Static OAuth for Remote Servers
```json
{
  "mcpServers": {
    "oauth-server": {
      "url": "https://api.example.com/mcp",
      "auth": {
        "CLIENT_ID": "your-oauth-client-id",
        "CLIENT_SECRET": "your-client-secret",
        "scopes": ["read", "write"]
      }
    }
  }
}
```

### Environment Variable Syntax
- **Config interpolation:** Supports `${env:VAR}`, `${userHome}`, `${workspaceFolder}`, `${workspaceFolderBasename}`, `${pathSeparator}`, `${/}`
- **Applied to fields:** `command`, `args`, `env`, `url`, `headers`
- **Example:** `"API_KEY": "${env:API_KEY}"`

### Configuration Sharing
- **Shared across CLI and IDE:** Not explicitly documented

### Official CLI Commands
- **No official CLI command documented** for adding MCP servers
- Configuration is primarily through `mcp.json` files or the Customize UI

### Comment Preservation
- **Preserves comments:** JSON format does not support comments

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented

### Restart Required
- **Restart required:** Yes (save file and restart Cursor)

### Additional Notes
- **Static OAuth redirect URLs:**
  - Web: `https://mcp.cursor.com/oauth/callback`
  - Desktop: `http://localhost:8787/callback`
- **Extension API:** Programmatic registration via `vscode.cursor.mcp.registerServer()` available
- **Config interpolation:** Environment variables and workspace variables supported
- **Enterprise controls:** Team MCP distribution, MCP Allowlist, network controls, user MCP extensions
- **OAuth scopes:** Can be specified in `auth.scopes` or discovered via `/.well-known/oauth-authorization-server`

---

## VS Code (GitHub Copilot)

### Configuration Path
- **Workspace:** `.vscode/mcp.json` in project (shared via version control)
- **User profile:** User profile folder (run "MCP: Open User Configuration" command)
- **Remote:** Remote user settings (run "MCP: Open Remote User Configuration")
- **Dev Container:** `devcontainer.json` under `customizations.vscode.mcp`

### Format
- **File format:** JSON
- **Schema:** JSON with `servers` top-level object (note: different from Cursor/Claude which use `mcpServers`)
- **IntelliSense:** Available for configuration file

### Scope Support
- **Workspace:** Project-specific, shared with team
- **User profile:** Available across all workspaces
- **Multiple profiles:** Each profile can have its own MCP server configuration

### Supported Transports
- **stdio:** Yes
- **http:** Yes
- **sse:** Yes (VS Code tries HTTP Stream first, falls back to SSE)

### Configuration Schema

#### STDIO Servers
```json
{
  "servers": {
    "server-name": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@microsoft/mcp-server-playwright"],
      "cwd": "${workspaceFolder}",
      "env": {
        "API_KEY": "${input:api-key}"
      },
      "envFile": "${workspaceFolder}/.env",
      "dev": {
        "watch": "src/**/*.ts"
      },
      "sandboxEnabled": true
    }
  }
}
```

#### HTTP/SSE Servers
```json
{
  "servers": {
    "server-name": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp",
      "headers": {
        "Authorization": "Bearer ${input:api-token}"
      }
    }
  }
}
```

#### Input Variables (for sensitive data)
```json
{
  "inputs": [
    {
      "type": "promptString",
      "id": "api-key",
      "description": "GitHub Personal Access Token",
      "password": true
    }
  ]
}
```

#### Sandbox Configuration (macOS/Linux only)
```json
{
  "sandbox": {
    "filesystem": {
      "allowWrite": ["/tmp"],
      "denyRead": ["/etc"],
      "denyWrite": ["/etc"]
    },
    "network": {
      "allowedDomains": ["*.example.com"],
      "deniedDomains": ["malicious.com"]
    }
  }
}
```

#### Dev Container Configuration
```json
{
  "image": "mcr.microsoft.com/devcontainers/typescript-node:latest",
  "customizations": {
    "vscode": {
      "mcp": {
        "servers": {
          "playwright": {
            "command": "npx",
            "args": ["-y", "@microsoft/mcp-server-playwright"]
          }
        }
      }
    }
  }
}
```

### Environment Variable Syntax
- **Input variables:** `${input:variable-id}` prompts user for value
- **Predefined variables:** `${workspaceFolder}`, `${userHome}`, etc.
- **Environment files:** `envFile` field to load variables from `.env` file

### Configuration Sharing
- **Shared across CLI and IDE:** Not explicitly documented

### Official CLI Commands
- **Add server:** `code --add-mcp "{\"name\":\"server-name\",\"command\":...}"`
- **Open config:** "MCP: Open User Configuration" command
- **Open workspace config:** "MCP: Open Workspace Folder Configuration" command
- **List servers:** "MCP: List Servers" command

### Comment Preservation
- **Preserves comments:** JSON format does not support comments

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented

### Restart Required
- **Restart required:** Not explicitly documented, but typical for config changes

### Additional Notes
- **Auto-discovery:** With `chat.mcp.discovery.enabled` setting, can detect MCP configs from other apps (e.g., Claude Desktop)
- **Sandbox support:** Only available on macOS and Linux for stdio servers
- **Remote support:** Servers run where configured; user profile runs locally, workspace runs on remote if connected
- **Input variables:** Secure way to handle sensitive information without hardcoding
- **Development mode:** `dev.watch` field for file watching during development
- **Tool approval:** Configurable per-server and per-tool approval modes

---

## Windsurf (Codeium Cascade)

### Configuration Path
- **Global:** `~/.codeium/windsurf/mcp_config.json` (macOS/Linux)
- **Global:** `%USERPROFILE%\.codeium\windsurf\mcp_config.json` (Windows)
- **Project-level:** Not supported - only global configuration

### Format
- **File format:** JSON
- **Schema:** JSON with `mcpServers` top-level object

### Scope Support
- **Global:** Available across all Windsurf projects
- **Project-level:** Not supported

### Supported Transports
- **stdio:** Yes
- **http:** Yes
- **sse:** Yes

### Configuration Schema

#### STDIO Servers
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "mcp-server"],
      "env": {
        "API_KEY": "${env:API_KEY}"
      }
    }
  }
}
```

#### HTTP/SSE Servers
```json
{
  "mcpServers": {
    "server-name": {
      "serverUrl": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:API_TOKEN}"
      }
    }
  }
}
```

### Environment Variable Syntax
- **Config interpolation:** Supports `${env:VAR}` in `command`, `args`, `env`, `serverUrl`, `url`, and `headers`
- **Applied to fields:** All fields support interpolation

### Configuration Sharing
- **Shared across CLI and IDE:** Not explicitly documented

### Official CLI Commands
- **No official CLI command documented** for adding MCP servers
- Configuration is through MCP Store UI or editing `mcp_config.json` directly

### Comment Preservation
- **Preserves comments:** JSON format does not support comments

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented

### Restart Required
- **Restart required:** Yes - MCP servers load at startup only, full restart required

### Additional Notes
- **Key difference:** Uses `serverUrl` instead of `url` for remote HTTP/SSE servers
- **Tool limit:** Hard limit of 100 tools across all connected MCP servers
- **Config location:** `~/.codeium/windsurf/` not `~/.windsurf/`
- **File name:** `mcp_config.json` not `mcp.json`
- **OAuth support:** Yes, with OAuth for each transport type
- **Admin controls:** Teams and Enterprise can allowlist approved MCP servers

---

## Antigravity (Google)

### Configuration Path
- **Global:** `~/.gemini/antigravity/mcp_config.json`
- **Project-level:** `.agent/mcp_config.json` in project folder

### Format
- **File format:** JSON
- **Schema:** JSON with `mcpServers` top-level object

### Scope Support
- **Global:** Available across all Antigravity projects
- **Project-level:** Available in current project via `.agent` folder

### Supported Transports
- **stdio:** Yes
- **http:** Yes
- **sse:** Yes

### Configuration Schema

#### STDIO Servers
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "mcp-server"],
      "env": {
        "API_KEY": "value"
      }
    }
  }
}
```

#### HTTP/SSE Servers
```json
{
  "mcpServers": {
    "server-name": {
      "type": "http",
      "url": "https://mcp.example.com/mcp",
      "headers": {
        "Authorization": "Bearer value"
      }
    }
  }
}
```

### Environment Variable Syntax
- **Config interpolation:** **NOT SUPPORTED** - Antigravity does not support `${VAR}` interpolation
- **All values:** Must be literal strings

### Configuration Sharing
- **Shared across CLI and IDE:** Yes - Antigravity 2.x IDE, `agy` CLI, and SDK share one central MCP config

### Official CLI Commands
- **No official CLI command documented** for adding MCP servers
- Configuration is through MCP Store UI or editing `mcp_config.json` directly

### Comment Preservation
- **Preserves comments:** JSON format does not support comments

### Unknown Fields
- **Preserves unknown fields:** Not explicitly documented

### Restart Required
- **Restart required:** Yes - agent session needs to be restarted for changes to take effect

### Additional Notes
- **Project folder:** Uses `.agent` folder (different from other clients)
- **No env interpolation:** Critical limitation - cannot use `${VAR}` syntax
- **Google Cloud integration:** Supports remote MCP servers for Google Cloud services (AlloyDB, BigQuery, Cloud SQL, etc.)
- **OAuth support:** Yes, with Google credentials OAuth

---

## Summary Comparison

| Feature | Codex | Claude Code | Cursor | VS Code | Windsurf | Antigravity |
|---------|-------|-------------|--------|---------|----------|-------------|
| **User config path** | `~/.codex/config.toml` | `~/.claude.json` | `~/.cursor/mcp.json` | User profile `mcp.json` | `~/.codeium/windsurf/mcp_config.json` | `~/.gemini/antigravity/mcp_config.json` |
| **Project config path** | `.codex/config.toml` | `.mcp.json` | `.cursor/mcp.json` | `.vscode/mcp.json` | Not supported | `.agent/mcp_config.json` |
| **File format** | TOML | JSON | JSON | JSON | JSON | JSON |
| **Top-level key** | `[mcp_servers]` | `mcpServers` | `mcpServers` | `servers` | `mcpServers` | `mcpServers` |
| **stdio transport** | Yes | Yes | Yes | Yes | Yes | Yes |
| **http transport** | Yes (streamable-http) | Yes | Yes | Yes | Yes | Yes |
| **sse transport** | No | Yes | Yes | Yes | Yes | Yes |
| **ws transport** | No | Yes | No | No | No | No |
| **Env var syntax** | `env_vars = ["VAR"]` | Direct in `env` | `${env:VAR}` | `${input:var-id}` | `${env:VAR}` | Not supported |
| **CLI add command** | `codex mcp add` | `claude mcp add` | None | `code --add-mcp` | None | None |
| **Comments preserved** | Yes (with extension) | No (JSON) | No (JSON) | No (JSON) | No (JSON) | No (JSON) |
| **Restart required** | Yes | Yes | Yes | Likely | Yes | Yes |
| **Shared CLI/IDE** | Yes | Not documented | Not documented | Not documented | Not documented | Yes |
| **Sandbox support** | No | No | No | Yes (macOS/Linux) | No | No |
| **OAuth support** | Yes | Yes | Yes (static) | Via headers | Yes | Yes |
| **Config interpolation** | No | `${VAR}` | `${env:VAR}` | `${input:var-id}` | `${env:VAR}` | No |
| **Remote URL key** | `url` | `url` | `url` | `url` | `serverUrl` | `url` |

---

## Key Implementation Considerations

### 1. Top-Level Key Differences
- **Codex:** Uses `mcp_servers` (TOML table)
- **Claude Code, Cursor, Windsurf, Antigravity:** Use `mcpServers` (JSON object)
- **VS Code:** Uses `servers` (JSON object) - **critical difference**

### 2. Transport Naming
- **Codex:** Uses "streamable-http" in docs, but likely accepts "http"
- **Claude Code:** Accepts both "http" and "streamable-http" as aliases
- **Cursor & VS Code:** Use "http"

### 3. Environment Variable Handling
- **Codex:** Uses `env_vars` array with optional `source` field
- **Claude Code:** Direct values in `env` object, with `${VAR}` expansion
- **Cursor:** Config interpolation with `${env:VAR}` syntax
- **VS Code:** Input variables with `${input:var-id}` for sensitive data
- **Windsurf:** Config interpolation with `${env:VAR}` syntax
- **Antigravity:** **NOT SUPPORTED** - all values must be literal strings

### 4. Scope Models
- **Codex:** User and project (trusted projects only)
- **Claude Code:** Three scopes (local, project, user) with distinct semantics
- **Cursor:** Global and project with merge behavior
- **VS Code:** Workspace and user profile, plus remote and Dev Container support
- **Windsurf:** Global only (no project-level configuration)
- **Antigravity:** Global and project (via `.agent` folder)

### 5. Additional Features
- **Codex:** Extensive tool approval modes, timeout configurations
- **Claude Code:** WebSocket support, dynamic headers, OAuth metadata override
- **Cursor:** Static OAuth, config interpolation, enterprise controls
- **VS Code:** Sandbox configuration, input variables, development mode, auto-discovery
- **Windsurf:** Uses `serverUrl` for remote servers, 100 tool limit, admin controls
- **Antigravity:** No environment variable interpolation, Google Cloud integration

---

## Documentation Sources

- **Codex:** https://learn.chatgpt.com/docs/extend/mcp, https://developers.openai.com/codex/config-reference
- **Claude Code:** https://code.claude.com/docs/en/mcp
- **Cursor:** https://cursor.com/docs/mcp
- **VS Code:** https://code.visualstudio.com/docs/agent-customization/mcp-servers, https://code.visualstudio.com/docs/agents/reference/mcp-configuration
- **Windsurf:** https://docs.windsurf.com/plugins/cascade/mcp, https://stackmcp.dev/blog/setup-mcp-servers-windsurf
- **Antigravity:** https://agentpedia.codes/blog/antigravity-mcp-tutorial, https://aidevhub.net/blog/google-antigravity-mcp-custom-tools
