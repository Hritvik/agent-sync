# Agent Skills Compatibility Matrix

**Last Updated:** October 29, 2026 (Codex section; other clients retain earlier research)

This document documents the current Agent Skills support for supported clients based on the verification dates noted per client. Unchanged client sections retain August 4, 2026 research.

## Overview

Agent Skills is an open standard for packaging instructions, resources, and optional scripts so AI agents can follow workflows reliably. The specification is defined at https://agentskills.io/specification.

Each MCP-compatible client has different support for Agent Skills, with varying locations, formats, and capabilities.

---

## Codex (OpenAI)

Verified October 29, 2026 against [official skill documentation](https://learn.chatgpt.com/docs/build-skills).

- **Personal:** `~/.agents/skills/<name>/SKILL.md`.
- **Project:** `.agents/skills` from the current directory up to the repository root.
- **Legacy:** this adapter retains `~/.codex/skills` discovery for existing installations;
  this legacy path is not listed in the current official discovery table.
- **Symlinks:** supported; Codex follows skill-folder symlinks.
- **Format:** `SKILL.md` with `name` and `description`, optional scripts, references,
  assets, and `agents/openai.yaml` for appearance, invocation policy, and tool dependencies.
- **Invocation:** explicit `$skill` or implicit matching by description.
- **Reload:** changes are detected automatically; restart if an update does not appear.
  Restart after changing skill configuration in `~/.codex/config.toml`.
- **Duplicates:** skills with matching names are not merged; both may appear in selectors.
- **Disable:** use `[[skills.config]]` with the exact `SKILL.md` path and `enabled = false`.

### Adapter behavior

`native` is preferred because the canonical `~/.agents/skills` store is already
visible to Codex. Native installation verifies that a skill exists in a discovery
location and matches its supplied local source; it does not copy content. An
external authored source can be installed explicitly with `symlink`. Project
installation targets `$CWD/.agents/skills`; callers should run from the intended
project folder. Existing destinations, including broken symlinks, are preserved.
`user` and the CLI's `personal` scope name are equivalent.

The adapter does not implement copy or plugin installation. It refuses to remove
existing skills because the adapter API has no installation ownership state:
shared canonical files and links may also serve other clients. Disable an exact
Codex skill path instead. Legacy imports remain an explicit separate action.

### T3 Alpha / T3 Code with Codex

Verified against the installed T3 Code (Beta) 0.1.3, commit `d2c440312e5f`,
on October 29, 2026: bundled server `apps/server/dist/binCli-tZsVKo_d.mjs`
calls `skills/list` with `cwds: [input.cwd]`.

T3 Code is a frontend to the selected provider. With the Codex provider, skill
listing is delegated to Codex's `skills/list` with the project's working directory;
there is no independent T3 skill store to synchronize. Default provider homes can
share local Codex discovery, while an isolated provider home may require separate
configuration. Plugin availability must be verified in that provider session;
installed files alone do not prove loading. Other T3 providers are not covered by
this adapter.

---

## OpenCode V2 in T3

Verified October 29, 2026 using OpenCode v2.1.4 and installed T3 Code (Beta) 0.1.3.
[Official V2 documentation](https://opencode.ai/v2/docs/skills) lists global
`~/.config/opencode/skills`, compatibility `~/.agents/skills` and
`~/.claude/skills`, and project `.opencode/skills`, `.agents/skills`, and
`.claude/skills`. OpenCode IDs derive from paths; later sources can override IDs.

T3 delegates its inventory to OpenCode `skill.list` with the workspace location.
CLIProxyAPI (`cliproxy`), Free Pool (`freellmpool`), and `fp2` are model providers
inside this same runtime, so discovery does not depend on selecting one of them.
Agent permissions and provider/model support for tool calls govern loading and use.

Use the skills repository's `scripts/install-codex.sh` for authored skills in the
shared discovery folder. For additional enabled Codex-only standalone/plugin
skill instructions, use that repository's `scripts/sync-opencode-skills.py` bridge.
The bridge owns only its new OpenCode links; do not also manage those destinations
with another synchronizer. It does not install Codex hooks, MCP tools, or plugin
runtime features. No separate OpenCode adapter is registered in agent-sync yet;
MCP configuration remains outside this bridge's scope.

---

## Claude Code (Anthropic)

### Skill Locations
- **Personal:** `~/.claude/skills/`
- **Project:** `.claude/skills/`

### Format
- **File format:** YAML frontmatter + Markdown body
- **Specification:** Follows Agent Skills specification with Claude-specific extensions
- **File name:** Must be exactly `SKILL.md`

### Scope Support
- **Personal:** Yes - `~/.claude/skills/`
- **Project:** Yes - `.claude/skills/`

### Frontmatter Support

#### Required Fields
- `name` (max 64 chars, lowercase letters, numbers, hyphens only)
- `description` (max 1024 chars for spec, 200 chars for Claude.ai uploads)

#### Optional Fields
- `license`
- `compatibility`
- `metadata`
- `allowed-tools` (CLI only, not SDK)
- `disable-model-invocation`
- `arguments`

#### Claude-Specific Extensions
- `disable-model-invocation`: When true, Claude cannot fire skill automatically
- `allowed-tools`: Pre-approve tools (CLI only)
- `arguments`: Define named arguments for skill invocation

### Directory Structure
```
skill-name/
├── SKILL.md          # Required
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

### Symlink Support
- **Symlinks:** Not explicitly documented
- **Symlink strategy:** Unknown

### External Directory Support
- **External directory:** Supported via `plugins` option in SDK
- **CLI support:** Not explicitly documented

### Copy vs Link
- **Strategy:** Claude reads directly from skill directories
- **Native support:** Yes - can read from canonical location if configured

### Reload Behavior
- **Reload:** Skills discovered at startup
- **Restart required:** Yes - must restart Claude Code to load new skills

### Local vs Remote Sessions
- **Local sessions:** Skills available
- **Remote/cloud sessions:** Not explicitly documented

### Scripts and Supporting Files
- **Scripts:** Supported in `scripts/` directory
- **References:** Supported in `references/` directory
- **Assets:** Supported in `assets/` directory
- **Dependencies:** Can declare in frontmatter for package installation

### Invocation Conventions
- **Implicit invocation:** Based on skill description
- **Explicit invocation:** `/skill-name` syntax
- **Arguments:** `$ARGUMENTS`, `$0`, `$1`, or named arguments via frontmatter

### Conflicts and Precedence
- **Duplicate names:** Not explicitly documented
- **Precedence:** Project skills override personal skills

### Additional Notes
- **Custom commands merged:** `.claude/commands/` and `.claude/skills/` both create commands
- **Dynamic context injection:** Supports `!command` syntax to inline command output
- **Subagent execution:** Can run skills in subagent
- **Tool restrictions:** `allowed-tools` only works in CLI, not SDK
- **Compatibility:** Claude.ai limits descriptions to 200 characters (vs 1024 in spec)

---

## GitHub Copilot

### Skill Locations
- **Personal:** `~/.copilot/skills/` or `~/.agents/skills/`
- **Project:** `.github/skills/`, `.claude/skills/`, or `.agents/skills/`

### Format
- **File format:** YAML frontmatter + Markdown body
- **Specification:** Follows Agent Skills specification
- **File name:** Must be exactly `SKILL.md`

### Scope Support
- **Personal:** Yes - `~/.copilot/skills/` or `~/.agents/skills/`
- **Project:** Yes - `.github/skills/`, `.claude/skills/`, or `.agents/skills/`

### Frontmatter Support

#### Required Fields
- `name` (lowercase, hyphens for spaces, matches directory name)
- `description`

#### Optional Fields
- `license`
- `allowed-tools`

#### Copilot-Specific Extensions
- None documented beyond standard Agent Skills spec

### Directory Structure
```
skill-name/
├── SKILL.md          # Required
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
└── assets/           # Optional: templates, resources
```

### Symlink Support
- **Symlinks:** Not explicitly documented
- **Symlink strategy:** Unknown

### External Directory Support
- **External directory:** Not documented
- **CLI support:** Can use `gh skill` to discover and install from GitHub

### Copy vs Link
- **Strategy:** Copilot reads directly from skill directories
- **Native support:** Yes - can read from `~/.agents/skills/` canonical location

### Reload Behavior
- **Reload:** Skills discovered at startup
- **Restart required:** Yes - must restart Copilot to load new skills

### Local vs Remote Sessions
- **Local sessions:** Skills available
- **Remote/cloud sessions:** Skills available in cloud agent

### Scripts and Supporting Files
- **Scripts:** Supported in skill directory
- **References:** Supported in skill directory
- **Assets:** Supported in skill directory

### Invocation Conventions
- **Implicit invocation:** Based on skill description
- **Explicit invocation:** Not explicitly documented
- **Tool approval:** `allowed-tools` pre-approves tools to avoid prompts

### Conflicts and Precedence
- **Duplicate names:** Not explicitly documented
- **Precedence:** Not explicitly documented

### Additional Notes
- **Multiple locations:** Supports `.github/skills/`, `.claude/skills/`, `.agents/skills/` for project skills
- **CLI support:** `gh skill` command for discovery and installation
- **Security warning:** Pre-approving `shell` or `bash` tools removes confirmation step
- **Cross-platform:** Works with Copilot cloud agent, code review, CLI, app, and VS Code/JetBrains

---

## Summary Comparison

| Feature | Codex | Claude Code | GitHub Copilot |
|---------|-------|-------------|----------------|
| **Personal skill path** | `~/.agents/skills/` (legacy retained) | `~/.claude/skills/` | `~/.copilot/skills/` or `~/.agents/skills/` |
| **Project skill path** | `.agents/skills/` | `.claude/skills/` | `.github/skills/`, `.claude/skills/`, `.agents/skills/` |
| **Recursive discovery** | Repository ancestor locations; arbitrary recursion not asserted | No | No |
| **Symlink support** | Supported | Unknown | Unknown |
| **External directory** | Through skill-folder symlinks | SDK only | No |
| **Copy strategy** | Native or symlink; copy unimplemented | Native | Native |
| **Restart required** | Automatic; restart fallback | Yes | Yes |
| **Remote sessions** | Unknown | Unknown | Yes |
| **Scripts supported** | Yes | Yes | Yes |
| **References supported** | Yes | Yes | Yes |
| **Assets supported** | Yes | Yes | Yes |
| **allowed-tools** | No approval guarantee | CLI only | Yes |
| **disable-model-invocation** | Use openai.yaml invocation policy | Yes | No |
| **arguments** | No | Yes | No |
| **Dynamic context injection** | No | Yes | No |
| **Canonical location support** | Yes (`~/.agents/skills/`) | No | Yes (`~/.agents/skills/`) |

---

## Key Implementation Considerations

### 1. Canonical Location Strategy
- **GitHub Copilot:** Natively supports `~/.agents/skills/` - can use `native` strategy
- **Codex:** Natively reads `~/.agents/skills/`; use `native` for canonical skills or `symlink` for external authored sources.
- **Claude Code:** Does not natively support `~/.agents/skills/` - requires `symlink` or `copy` strategy

### 2. Symlink Strategy
- **Codex:** Follows symlinked skill folders.
- **Claude Code:** Unknown - needs testing
- **GitHub Copilot:** Unknown - needs testing

### 3. Copy Strategy
- Use when symlinks are not supported
- Must track copied skills in state file
- Must detect drift between canonical and copied versions
- Canonical skill remains authoritative

### 4. Frontmatter Compatibility
- **Codex:** Keep provider-specific behavior in the appropriate metadata; do not assume Claude/Copilot tool permissions transfer.
- **Claude Code:** Supports `disable-model-invocation`, `allowed-tools`, `arguments` - may not be portable
- **GitHub Copilot:** Supports `allowed-tools` - portable to Claude Code CLI but not SDK

### 5. Skill Name Constraints
- **Codex:** The current guide requires a name; agent-sync enforces the portable 64-character convention.
- **Claude Code:** Max 64 chars, lowercase letters, numbers, hyphens only
- **GitHub Copilot:** Lowercase, hyphens for spaces
- **Recommendation:** Use Claude Code constraints for maximum portability

### 6. Description Length Constraints
- **Codex:** The current guide requires a description; agent-sync enforces the portable 1024-character maximum.
- **Claude Code:** Max 1024 chars (spec), 200 chars (Claude.ai uploads)
- **GitHub Copilot:** Not explicitly limited
- **Recommendation:** Use 200 chars for maximum portability

### 7. Invocation Differences
- **Codex:** `$skill` syntax
- **Claude Code:** `/skill-name` syntax
- **GitHub Copilot:** Implicit only
- **Recommendation:** Document invocation differences in compatibility reports

### 8. Tool Approval Differences
- **Codex:** Do not infer tool approval from a skill; provider permissions remain authoritative.
- **Claude Code:** `allowed-tools` works in CLI only, not SDK
- **GitHub Copilot:** `allowed-tools` works
- **Recommendation:** Warn about tool approval differences

---

## Documentation Sources

- **Codex:** https://developers.openai.com/codex/skills, https://github.com/openai/codex/blob/main/docs/skills.md
- **Claude Code:** https://code.claude.com/docs/en/skills, https://agentskills.io/specification
- **GitHub Copilot:** https://docs.github.com/en/copilot/concepts/agents/about-agent-skills, https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills
- **Agent Skills Specification:** https://agentskills.io/specification
