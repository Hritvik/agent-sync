# agent-sync

Universal Agent Extension Manager - Define MCP servers and Agent Skills once, configure across multiple clients.

## Problem

Every AI agent (Codex, Claude Code, Cursor, VS Code, GitHub Copilot, Windsurf, Antigravity) stores its extensions in different locations and formats:

- **MCP servers** for tool integrations
- **Agent Skills** for domain knowledge and workflows

Managing the same extensions across multiple agents requires manual duplication and maintenance.

## Solution

`agent-sync` provides canonical registries for both MCP servers and Agent Skills, automatically generating or updating client-specific configurations through adapters.

```
One canonical MCP registry + One canonical skill store
            ↓
Client-specific adapters
            ↓
Codex / Claude / Cursor / VS Code / Copilot / Windsurf / Antigravity / other configs
```

## Installation

```bash
# Install with uv
uv tool install .

# Or from local directory
uv sync
uv run agent-sync --help
```

## Quick Start

### MCP Servers

```bash
# Initialize configuration
agent-sync init

# Edit your servers
$EDITOR ~/.config/agent-sync/servers.yaml

# Validate configuration
agent-sync mcp validate

# Check for issues
agent-sync mcp doctor

# Preview changes
agent-sync mcp diff

# Apply to all detected clients
agent-sync mcp apply
```

### Agent Skills

```bash
# Import skills from existing client
agent-sync skills import --from codex

# List all skills
agent-sync skills list

# Validate skills
agent-sync skills validate

# Preview changes
agent-sync skills diff

# Apply to all detected clients
agent-sync skills apply
```

### Both Extensions

```bash
# Apply both MCP servers and skills
agent-sync apply

# Apply to specific client
agent-sync apply --client claude
```

## Configuration

### MCP Server Registry

`~/.config/agent-sync/servers.yaml`:

```yaml
version: 1

defaults:
  enabled: true

servers:
  context7:
    description: Current library and framework documentation
    transport: http
    url: https://mcp.context7.com/mcp
    headers:
      Authorization:
        from_env: CONTEXT7_TOKEN
    enabled: true

  playwright:
    description: Browser automation
    transport: stdio
    command: npx
    args:
      - -y
      - "@playwright/mcp@latest"
    enabled: true

  github:
    description: GitHub repositories, issues, and pull requests
    transport: stdio
    command: docker
    args:
      - run
      - --rm
      - -i
      - -e
      - GITHUB_PERSONAL_ACCESS_TOKEN
      - ghcr.io/github/github-mcp-server
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN:
        from_env: GITHUB_PERSONAL_ACCESS_TOKEN
    enabled: true
```

### Profiles

`~/.config/agent-sync/profiles.yaml`:

```yaml
profiles:
  default:
    servers:
      - context7
      - github
      - playwright

  work:
    servers:
      - context7
      - github
      - company-jira
      - company-observability

  personal:
    servers:
      - context7
      - playwright
```

Usage:

```bash
agent-sync mcp apply --profile work
agent-sync mcp apply --profile personal --client cursor
```

### Agent Skills Store

`~/.agents/skills/` - Canonical skill directory:

```
~/.agents/skills/
├── fix-ci/
│   ├── SKILL.md
│   ├── scripts/
│   ├── references/
│   └── assets/
├── review-pr/
│   └── SKILL.md
└── frontend-design/
    └── SKILL.md
```

## Codex and T3 Code

Codex discovers personal skills in `~/.agents/skills` and project skills in
`.agents/skills`; legacy `~/.codex/skills` remains a compatibility location.
Keep authored content in the skills repository and use its installer for links.
Do not use two installation owners for the same collection.

T3 Code with the Codex provider delegates discovery to Codex's app-server, so
there is no separate T3 skills destination or adapter. This was verified in the
installed T3 Code (Beta) 0.1.3 on 2026-10-29. A different provider home or remote
machine needs separate verification; Claude and other providers use their own
loading rules. See [skill compatibility](docs/skill-compatibility.md).

## Supported Clients

- **Codex** (OpenAI) - `~/.codex/config.toml`
- **Claude Code** (Anthropic) - `~/.claude.json` and `.mcp.json`
- **Cursor** - `~/.cursor/mcp.json` and `.cursor/mcp.json`
- **VS Code** (GitHub Copilot) - `.vscode/mcp.json` and user profile
- **Windsurf** (Codeium Cascade) - `~/.codeium/windsurf/mcp_config.json`
- **Antigravity** (Google) - `~/.gemini/antigravity/mcp_config.json` and `.agent/mcp_config.json`

## Secret Handling

`mcp-sync` never writes resolved secret values to generated configurations unless explicitly required. Use environment variable references:

```yaml
env:
  API_TOKEN:
    from_env: API_TOKEN
```

Literal non-secret values:

```yaml
env:
  LOG_LEVEL:
    value: info
```

The tool warns when:
- Referenced environment variables are missing
- Literal values appear to be secrets
- Generated configs would contain plaintext credentials

## Commands

### MCP Servers
- `agent-sync mcp list` - Show canonical MCP servers
- `agent-sync mcp show <server>` - Show details for a specific server
- `agent-sync mcp clients` - Show detected clients and config destinations
- `agent-sync mcp validate` - Validate the canonical registry
- `agent-sync mcp diff` - Show planned changes without writing
- `agent-sync mcp apply` - Apply changes to client configurations
- `agent-sync mcp doctor` - Check configuration and environment
- `agent-sync mcp remove` - Remove managed servers from client configs
- `agent-sync mcp backup list` - List available backups
- `agent-sync mcp backup restore` - Restore from backup

### Agent Skills
- `agent-sync skills list` - Show canonical skills
- `agent-sync skills show <skill>` - Show details for a specific skill
- `agent-sync skills validate` - Validate skills
- `agent-sync skills inspect <skill>` - Security inspection of a skill
- `agent-sync skills import --from <client>` - Import skills from existing client
- `agent-sync skills diff` - Show planned changes without writing
- `agent-sync skills apply` - Apply changes to client configurations
- `agent-sync skills doctor` - Check skills and environment
- `agent-sync skills remove <name>` - Remove managed skill

### Both Extensions
- `agent-sync init` - Create starter configuration files
- `agent-sync validate` - Validate both registries
- `agent-sync doctor` - Check both configurations
- `agent-sync diff` - Show planned changes for both
- `agent-sync apply` - Apply changes for both

## Safety Features

- **Atomic writes** - Configurations are written atomically
- **Backups** - Automatic backups before modifications
- **Dry-run** - Preview changes before applying
- **Conflict detection** - Detects and reports conflicts instead of overwriting
- **Merge behavior** - Preserves non-MCP settings and unmanaged servers
- **Secret redaction** - Secrets never appear in logs, diffs, or diagnostics

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed architecture documentation.

## Adding a New Adapter

See [docs/adding-an-adapter.md](docs/adding-an-adapter.md) for guidance on adding support for a new MCP client.

## Limitations

- Does not install MCP servers - only configures them
- Does not automatically resolve missing commands or dependencies
- Windows support is experimental for version 1
- Some client-specific features may not be supported

## License

MIT

## Contributing

Contributions welcome! Please read the architecture documentation before submitting changes.
