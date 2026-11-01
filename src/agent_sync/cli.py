"""CLI commands for agent-sync."""

import json
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agent_sync import __version__
from agent_sync.adapters.antigravity import AntigravityAdapter
from agent_sync.adapters.claude import ClaudeAdapter
from agent_sync.adapters.codex import CodexAdapter
from agent_sync.adapters.cursor import CursorAdapter
from agent_sync.adapters.vscode import VSCodeAdapter
from agent_sync.adapters.windsurf import WindsurfAdapter
from agent_sync.backup import create_backup, list_backups, restore_backup
from agent_sync.exceptions import (
    AdapterError,
    ConflictError,
    ConfigNotFoundError,
    McpSyncError,
    UnsupportedFeatureError,
    ValidationError,
)
from agent_sync.merge import configs_are_equal, detect_conflicts
from agent_sync.paths import (
    ensure_config_dirs,
    get_backups_dir,
    get_config_dir,
    get_profiles_path,
    get_servers_path,
    get_skills_dir,
    get_skills_registry_path,
    get_state_path,
    ensure_skills_dir,
)
from agent_sync.redaction import check_env_vars_exist, extract_env_references, warn_about_secrets
from agent_sync.registry import filter_servers_by_client, filter_servers_by_profile, load_profiles, load_registry
from agent_sync.models import SkillSource
from agent_sync.skill_adapters import (
    AntigravitySkillAdapter,
    ClaudeSkillAdapter,
    CodexSkillAdapter,
    CopilotSkillAdapter,
    CursorSkillAdapter,
    VSCodeSkillAdapter,
    WindsurfSkillAdapter,
)
from agent_sync.skills import (
    compute_skill_hash,
    discover_skills,
    import_skills_from_codex,
    load_skill_from_directory,
    load_skill_registry,
    parse_skill_frontmatter,
    save_skill_registry,
    validate_all_skills,
    validate_skill_directory,
    validate_skill_frontmatter,
)
from agent_sync.state import (
    clear_client_state,
    get_client_state,
    is_server_managed,
    load_state,
    remove_server_from_state,
    update_client_state,
)

app = typer.Typer(
    name="agent-sync",
    help="Universal Agent Extension Manager - Define MCP servers and Agent Skills once, configure across multiple clients.",
    add_completion=False,
)
console = Console()

# All available adapters
ADAPTERS = {
    "codex": CodexAdapter(),
    "claude": ClaudeAdapter(),
    "cursor": CursorAdapter(),
    "vscode": VSCodeAdapter(),
    "windsurf": WindsurfAdapter(),
    "antigravity": AntigravityAdapter(),
}

# All available skill adapters for different clients
SKILL_ADAPTERS = {
    "codex": CodexSkillAdapter(),
    "claude": ClaudeSkillAdapter(),
    "copilot": CopilotSkillAdapter(),
    "windsurf": WindsurfSkillAdapter(),
    "cursor": CursorSkillAdapter(),
    "vscode": VSCodeSkillAdapter(),
    "antigravity": AntigravitySkillAdapter(),
}

# Create sub-apps for MCP and skills
mcp_app = typer.Typer(help="MCP server commands")
skills_app = typer.Typer(help="Agent Skills commands")
app.add_typer(mcp_app, name="mcp")
app.add_typer(skills_app, name="skills")


@app.command()
def init(
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration files"),
) -> None:
    """Initialize agent-sync configuration files."""
    ensure_config_dirs()
    ensure_skills_dir()

    servers_path = get_servers_path()
    profiles_path = get_profiles_path()
    skills_registry_path = get_skills_registry_path()

    # Check if files exist
    if servers_path.exists() and not force:
        console.print(f"[yellow]Servers configuration already exists at {servers_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    if profiles_path.exists() and not force:
        console.print(f"[yellow]Profiles configuration already exists at {profiles_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    if skills_registry_path.exists() and not force:
        console.print(f"[yellow]Skills registry already exists at {skills_registry_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    # Create example servers.yaml
    example_servers = """version: 1

defaults:
  enabled: true

servers:
  context7:
    description: Current library and framework documentation
    transport: http
    config:
      url: https://mcp.context7.com/mcp
      headers:
        Authorization:
          from_env: CONTEXT7_TOKEN
    enabled: true

  playwright:
    description: Browser automation
    transport: stdio
    config:
      command: npx
      args:
        - -y
        - "@playwright/mcp@latest"
    enabled: true

  github:
    description: GitHub repositories, issues, and pull requests
    transport: stdio
    config:
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
"""

    # Create example profiles.yaml
    example_profiles = """profiles:
  default:
    servers:
      - context7
      - github
      - playwright

  work:
    servers:
      - context7
      - github

  personal:
    servers:
      - context7
      - playwright
"""

    servers_path.write_text(example_servers)
    profiles_path.write_text(example_profiles)
    skills_registry_path.write_text("")

    console.print(f"[green]✓[/green] Created servers configuration at {servers_path}")
    console.print(f"[green]✓[/green] Created profiles configuration at {profiles_path}")
    console.print(f"[green]✓[/green] Created skills registry at {skills_registry_path}")
    console.print("\nEdit the servers configuration to add your MCP servers.")
    console.print("Import skills with: agent-sync skills import --from codex")
    console.print("Run [bold]agent-sync mcp validate[/bold] to check your configuration.")
    console.print("Run [bold]agent-sync mcp apply[/bold] to apply to detected clients.")


# ============================================================================
# MCP Commands
# ============================================================================

@mcp_app.command()
def validate() -> None:
    """Validate the canonical MCP registry without modifying anything."""
    try:
        registry = load_registry()
        console.print(f"[green]✓[/green] Registry is valid (version {registry.version})")
        console.print(f"  Found {len(registry.servers)} server(s)")
        
        for server_name, server_def in registry.servers.items():
            status = "[green]enabled[/green]" if server_def.enabled else "[yellow]disabled[/yellow]"
            console.print(f"  - {server_name}: {server_def.description} ({status})")
        
    except ConfigNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    except ValidationError as e:
        console.print(f"[red]✗[/red] Validation error: {e}")
        if e.server_name:
            console.print(f"  Server: {e.server_name}")
        if e.field:
            console.print(f"  Field: {e.field}")
        raise typer.Exit(1)
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def list_servers(
    profile_name: Optional[str] = typer.Option(None, "--profile", help="Filter servers by profile"),
) -> None:
    """Show canonical MCP servers and their status."""
    try:
        registry = load_registry()
        
        # Apply profile filter if specified
        if profile_name:
            profiles = load_profiles()
            registry = filter_servers_by_profile(registry, profiles, profile_name)
        
        table = Table(title="MCP Servers")
        table.add_column("Name", style="cyan")
        table.add_column("Transport", style="magenta")
        table.add_column("Enabled", style="green")
        table.add_column("Description")
        
        for server_name, server_def in registry.servers.items():
            enabled = "yes" if server_def.enabled else "no"
            table.add_row(
                server_name,
                server_def.transport.value,
                enabled,
                server_def.description,
            )
        
        console.print(table)
        
    except ConfigNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def show(server_name: str) -> None:
    """Show details for a specific server."""
    try:
        registry = load_registry()
        
        if server_name not in registry.servers:
            console.print(f"[red]✗[/red] Server not found: {server_name}")
            raise typer.Exit(1)
        
        server_def = registry.servers[server_name]
        
        console.print(f"[bold]Server:[/bold] {server_name}")
        console.print(f"[bold]Description:[/bold] {server_def.description}")
        console.print(f"[bold]Transport:[/bold] {server_def.transport.value}")
        console.print(f"[bold]Enabled:[/bold] {server_def.enabled}")
        
        # Show config details
        console.print(f"\n[bold]Configuration:[/bold]")
        config_dict = server_def.config.model_dump(exclude_none=True)
        console.print(json.dumps(config_dict, indent=2))
        
        # Show client filter
        if server_def.clients.include or server_def.clients.exclude:
            console.print(f"\n[bold]Client Filter:[/bold]")
            if server_def.clients.include:
                console.print(f"  Include: {', '.join(server_def.clients.include)}")
            if server_def.clients.exclude:
                console.print(f"  Exclude: {', '.join(server_def.clients.exclude)}")
        
    except ConfigNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def clients() -> None:
    """Show detected clients and their configuration destinations."""
    table = Table(title="Detected MCP Clients")
    table.add_column("Client", style="cyan")
    table.add_column("Detected", style="green")
    table.add_column("Config Path")
    
    for client_name, adapter in ADAPTERS.items():
        detected = adapter.detect()
        detected_str = "yes" if detected else "no"
        try:
            config_path = adapter.config_path()
            config_str = str(config_path)
        except AdapterError:
            config_str = "N/A"
        
        table.add_row(client_name, detected_str, config_str)
    
    console.print(table)


@mcp_app.command()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Check configuration and environment for issues."""
    issues = []
    
    # Check if registry exists
    servers_path = get_servers_path()
    if not servers_path.exists():
        issues.append(("error", f"Registry file not found: {servers_path}"))
    else:
        try:
            registry = load_registry()
            issues.append(("success", "Registry is valid"))
        except ValidationError as e:
            issues.append(("error", f"Registry validation error: {e}"))
        except Exception as e:
            issues.append(("error", f"Failed to load registry: {e}"))
    
    # Check client detection
    for client_name, adapter in ADAPTERS.items():
        if adapter.detect():
            issues.append(("success", f"{client_name} detected"))
        else:
            issues.append(("warning", f"{client_name} not detected"))
    
    # Check for missing environment variables
    try:
        registry = load_registry()
        env_refs = extract_env_references(registry.model_dump())
        missing = check_env_vars_exist(env_refs)
        for var in missing:
            issues.append(("warning", f"Environment variable not set: {var}"))
    except Exception:
        pass
    
    # Check for potential secrets in config
    try:
        registry = load_registry()
        warnings = warn_about_secrets(registry.model_dump())
        for warning in warnings:
            issues.append(("warning", warning))
    except Exception:
        pass
    
    # Output results
    if json_output:
        output = [{"level": level, "message": msg} for level, msg in issues]
        console.print(json.dumps(output, indent=2))
    else:
        for level, message in issues:
            if level == "error":
                console.print(f"[red]✗[/red] {message}")
            elif level == "warning":
                console.print(f"[yellow]![/yellow] {message}")
            else:
                console.print(f"[green]✓[/green] {message}")


@mcp_app.command()
def diff(
    client: Optional[str] = typer.Option(None, "--client", help="Show diff for specific client only"),
    profile_name: Optional[str] = typer.Option(None, "--profile", help="Filter servers by profile"),
) -> None:
    """Show planned changes without writing."""
    try:
        registry = load_registry()
        
        # Apply profile filter if specified
        if profile_name:
            profiles = load_profiles()
            registry = filter_servers_by_profile(registry, profiles, profile_name)
        
        # Filter clients if specified
        clients_to_check = [client] if client else list(ADAPTERS.keys())
        
        for client_name in clients_to_check:
            if client_name not in ADAPTERS:
                console.print(f"[red]✗[/red] Unknown client: {client_name}")
                continue
            
            adapter = ADAPTERS[client_name]
            
            console.print(f"\n[bold]{client_name.upper()}[/bold]")
            console.print(f"  Config path: {adapter.config_path()}")
            
            # Check for unsupported features
            warnings = adapter.validate_support(registry)
            for warning in warnings:
                console.print(f"  [yellow]![/yellow] {warning}")
            
            # Load existing config
            try:
                existing = adapter.load_config()
            except AdapterError as e:
                console.print(f"  [yellow]![/yellow] Failed to load config: {e}")
                existing = {}
            
            # Render new config
            filtered_registry = filter_servers_by_client(registry, client_name)
            generated = adapter.render_servers(filtered_registry)
            
            # Check for conflicts
            client_state = get_client_state(client_name)
            managed_servers = set(client_state.managed_servers.keys()) if client_state else set()
            conflicts = detect_conflicts(existing, generated, "mcpServers" if client_name != "vscode" else "servers", client_name, managed_servers)
            
            for conflict in conflicts:
                console.print(f"  [red]✗[/red] {conflict}")
            
            # Check if configs are equal
            if configs_are_equal(existing, generated):
                console.print(f"  [green]✓[/green] No changes needed")
            else:
                console.print(f"  [cyan]→[/cyan] Changes would be applied")
    
    except ConfigNotFoundError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def apply(
    client: Optional[str] = typer.Option(None, "--client", help="Apply to specific client only"),
    profile_name: Optional[str] = typer.Option(None, "--profile", help="Filter servers by profile"),
    scope: str = typer.Option("user", "--scope", help="Configuration scope (user or project)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing"),
    no_backup: bool = typer.Option(False, "--no-backup", help="Skip creating backups"),
    yes: bool = typer.Option(False, "--yes", help="Apply without confirmation"),
) -> None:
    """Apply changes to client configurations."""
    try:
        registry = load_registry()
        
        # Apply profile filter if specified
        if profile_name:
            profiles = load_profiles()
            registry = filter_servers_by_profile(registry, profiles, profile_name)
        
        # Filter clients if specified
        clients_to_apply = [client] if client else list(ADAPTERS.keys())
        
        for client_name in clients_to_apply:
            if client_name not in ADAPTERS:
                console.print(f"[red]✗[/red] Unknown client: {client_name}")
                continue
            
            adapter = ADAPTERS[client_name]
            
            console.print(f"\n[bold]{client_name.upper()}[/bold]")
            
            # Check for unsupported features
            warnings = adapter.validate_support(registry)
            for warning in warnings:
                console.print(f"  [yellow]![/yellow] {warning}")
            
            # Load existing config
            try:
                existing = adapter.load_config(scope)
            except AdapterError as e:
                console.print(f"  [yellow]![/yellow] Failed to load config: {e}")
                existing = {}
            
            # Render new config
            filtered_registry = filter_servers_by_client(registry, client_name)
            generated = adapter.render_servers(filtered_registry, scope)
            
            # Check for conflicts
            client_state = get_client_state(client_name)
            managed_servers = set(client_state.managed_servers.keys()) if client_state else set()
            conflicts = detect_conflicts(existing, generated, "mcpServers" if client_name != "vscode" else "servers", client_name, managed_servers)
            
            if conflicts:
                console.print(f"  [red]✗[/red] Conflicts detected:")
                for conflict in conflicts:
                    console.print(f"    {conflict}")
                console.print("  Use --on-conflict to specify conflict resolution policy")
                continue
            
            # Check if configs are equal
            if configs_are_equal(existing, generated):
                console.print(f"  [green]✓[/green] No changes needed")
                continue
            
            # Create backup unless disabled
            if not dry_run and not no_backup:
                config_path = adapter.config_path(scope)
                if config_path.exists():
                    backup_path = create_backup(config_path, client_name)
                    console.print(f"  [cyan]→[/cyan] Backup created: {backup_path}")
                    # Clean up old backups
                    from agent_sync.backup import cleanup_old_backups
                    cleanup_old_backups(client_name)
            
            # Merge configs
            merged = adapter.merge_config(existing, generated, scope)
            
            # Write config
            if dry_run:
                console.print(f"  [cyan]→[/cyan] Dry run - would write to {adapter.config_path(scope)}")
            else:
                if not yes:
                    console.print(f"  [cyan]→[/cyan] Would write to {adapter.config_path(scope)}")
                    if not typer.confirm("Proceed?"):
                        console.print("  Skipped")
                        continue
                
                adapter.write_config(merged, scope)
                console.print(f"  [green]✓[/green] Configuration written")
                
                # Update state
                from agent_sync.backup import compute_config_hash
                managed_servers_dict = {}
                for server_name in filtered_registry.servers.keys():
                    server_config = generated.get("mcpServers" if client_name != "vscode" else "servers", {}).get(server_name, {})
                    managed_servers_dict[server_name] = compute_config_hash(server_config)
                
                update_client_state(
                    client_name,
                    str(adapter.config_path(scope)),
                    managed_servers_dict,
                    __version__,
                )
        
        console.print("\n[green]✓[/green] Apply complete")
        
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def remove(
    server_name: str,
    client: Optional[str] = typer.Option(None, "--client", help="Remove from specific client only"),
    yes: bool = typer.Option(False, "--yes", help="Remove without confirmation"),
) -> None:
    """Remove a managed server from client configurations."""
    try:
        registry = load_registry()
        
        if server_name not in registry.servers:
            console.print(f"[red]✗[/red] Server not found: {server_name}")
            raise typer.Exit(1)
        
        clients_to_update = [client] if client else list(ADAPTERS.keys())
        
        for client_name in clients_to_update:
            if client_name not in ADAPTERS:
                console.print(f"[red]✗[/red] Unknown client: {client_name}")
                continue
            
            adapter = ADAPTERS[client_name]
            
            # Check if server is managed
            if not is_server_managed(client_name, server_name):
                console.print(f"  [yellow]![/yellow] {client_name}: Server not managed by mcp-sync")
                continue
            
            console.print(f"\n[bold]{client_name.upper()}[/bold]")
            
            if not yes:
                if not typer.confirm(f"Remove '{server_name}' from {client_name}?"):
                    console.print("  Skipped")
                    continue
            
            # Remove from state
            remove_server_from_state(client_name, server_name)
            
            # Reload and apply without this server
            filtered_registry = filter_servers_by_client(registry, client_name)
            if server_name in filtered_registry.servers:
                del filtered_registry.servers[server_name]
            
            existing = adapter.load_config()
            generated = adapter.render_servers(filtered_registry)
            merged = adapter.merge_config(existing, generated)
            
            # Create backup
            config_path = adapter.config_path()
            if config_path.exists():
                backup_path = create_backup(config_path, client_name)
                console.print(f"  [cyan]→[/cyan] Backup created: {backup_path}")
            
            adapter.write_config(merged)
            console.print(f"  [green]✓[/green] Server removed from configuration")
        
        console.print("\n[green]✓[/green] Remove complete")
        
    except McpSyncError as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(1)


@mcp_app.command()
def backup_list(client: Optional[str] = typer.Option(None, "--client", help="List backups for specific client")):
    """List available backups."""
    clients_to_list = [client] if client else list(ADAPTERS.keys())
    
    for client_name in clients_to_list:
        if client_name not in ADAPTERS:
            console.print(f"[red]✗[/red] Unknown client: {client_name}")
            continue
        
        console.print(f"\n[bold]{client_name.upper()}[/bold]")
        backups = list_backups(client_name)
        
        if not backups:
            console.print("  No backups found")
        else:
            for backup in backups:
                console.print(f"  {backup.name}")


@mcp_app.command()
def backup_restore(
    backup_file: str,
    client: str = typer.Argument(..., help="Client name"),
) -> None:
    """Restore a configuration from backup."""
    if client not in ADAPTERS:
        console.print(f"[red]✗[/red] Unknown client: {client}")
        raise typer.Exit(1)
    
    adapter = ADAPTERS[client]
    backup_path = Path(backup_file)
    
    if not backup_path.exists():
        console.print(f"[red]✗[/red] Backup file not found: {backup_file}")
        raise typer.Exit(1)
    
    config_path = adapter.config_path()
    
    if not typer.confirm(f"Restore {backup_file} to {config_path}?"):
        console.print("Cancelled")
        return
    
    try:
        restore_backup(backup_path, config_path)
        console.print(f"[green]✓[/green] Backup restored")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to restore: {e}")
        raise typer.Exit(1)


# ============================================================================
# Skills Commands
# ============================================================================

@skills_app.command()
def list_skills() -> None:
    """Show canonical Agent Skills and their status."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dirs = discover_skills(skills_dir)
    registry = load_skill_registry()
    
    if not skill_dirs:
        console.print("[yellow]No skills found in canonical store[/yellow]")
        console.print(f"  Location: {skills_dir}")
        console.print("Import skills with: agent-sync skills import --from codex")
        return
    
    table = Table(title="Agent Skills")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Source", style="magenta")
    table.add_column("Trust", style="yellow")
    table.add_column("Enabled", style="green")
    
    for skill_dir in sorted(skill_dirs):
        skill_name = skill_dir.name
        if skill_name in registry.skills:
            skill_def = registry.skills[skill_name]
            source_type = skill_def.source.type
            trust = skill_def.trust_state
            enabled = "yes" if skill_def.enabled else "no"
            description = skill_def.description[:50] + "..." if len(skill_def.description) > 50 else skill_def.description
        else:
            source_type = "unknown"
            trust = "unreviewed"
            enabled = "yes"
            # Load description from SKILL.md
            try:
                frontmatter = parse_skill_frontmatter(skill_dir / "SKILL.md")
                description = frontmatter.get("description", "")[:50] + "..." if len(frontmatter.get("description", "")) > 50 else frontmatter.get("description", "")
            except:
                description = "N/A"
        
        table.add_row(skill_name, description, source_type, trust, enabled)
    
    console.print(table)
    console.print(f"\nTotal: {len(skill_dirs)} skill(s)")


@skills_app.command()
def import_skills(
    from_client: str = typer.Option(..., "--from", help="Client to import from (codex, claude, copilot)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be imported without making changes"),
    copy: bool = typer.Option(False, "--copy", help="Copy instead of move (default: move)"),
) -> None:
    """Import skills from an existing client to the canonical store."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    if from_client == "codex":
        results = import_skills_from_codex(skills_dir, dry_run=dry_run, copy_mode=copy)
    else:
        console.print(f"[red]✗[/red] Import from {from_client} not yet implemented")
        console.print("Supported clients: codex")
        raise typer.Exit(1)
    
    # Display results
    table = Table(title=f"Import Results from {from_client.capitalize()}")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Message")
    
    for skill_name, status, message in results:
        status_color = "green" if status in ["dry-run", "moved", "copied", "skipped"] else "yellow" if status == "conflict" else "red"
        table.add_row(skill_name, f"[{status_color}]{status}[/{status_color}]", message)
    
    console.print(table)
    
    # Summary
    total = len(results)
    success = sum(1 for _, s, _ in results if s in ["dry-run", "moved", "copied"])
    skipped = sum(1 for _, s, _ in results if s == "skipped")
    conflict = sum(1 for _, s, _ in results if s == "conflict")
    error = sum(1 for _, s, _ in results if s == "error")
    
    console.print(f"\nSummary: {total} total, {success} success, {skipped} skipped, {conflict} conflict, {error} error")


@skills_app.command()
def validate_skills() -> None:
    """Validate all skills in the canonical store."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    results = validate_all_skills(skills_dir)
    
    if not results:
        console.print("[yellow]No skills found in canonical store[/yellow]")
        return
    
    table = Table(title="Skill Validation Results")
    table.add_column("Skill", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Message")
    
    valid_count = 0
    for skill_dir, error in results:
        skill_name = skill_dir.name
        if error is None:
            table.add_row(skill_name, "[green]✓ Valid[/green]", "")
            valid_count += 1
        else:
            table.add_row(skill_name, "[red]✗ Invalid[/red]", error.message)
    
    console.print(table)
    console.print(f"\n{valid_count}/{len(results)} skills are valid")


@skills_app.command()
def show(skill_name: str) -> None:
    """Show details for a specific skill."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dir = skills_dir / skill_name
    if not skill_dir.exists():
        console.print(f"[red]✗[/red] Skill not found: {skill_name}")
        raise typer.Exit(1)
    
    # Load skill definition
    try:
        source = SkillSource(type="local", path=str(skill_dir))
        skill_def = load_skill_from_directory(skill_dir, source)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load skill: {e}")
        raise typer.Exit(1)
    
    console.print(f"[bold]Skill:[/bold] {skill_name}")
    console.print(f"[bold]Description:[/bold] {skill_def.description}")
    console.print(f"[bold]Source:[/bold] {skill_def.source.type} from {skill_def.source.origin}")
    console.print(f"[bold]Trust State:[/bold] {skill_def.trust_state}")
    console.print(f"[bold]Enabled:[/bold] {skill_def.enabled}")
    console.print(f"[bold]Content Hash:[/bold] {skill_def.content_hash[:16]}...")
    
    # Show supporting files
    console.print(f"\n[bold]Supporting Files:[/bold]")
    for file_path in skill_def.supporting_files:
        console.print(f"  - {file_path}")
    
    # Show client compatibility
    console.print(f"\n[bold]Client Compatibility:[/bold]")
    for client_name, adapter in SKILL_ADAPTERS.items():
        if adapter.detect():
            report = adapter.inspect_compatibility(skill_def)
            status_color = "green" if report.is_compatible() else "yellow" if report.status.value == "requires-adaptation" else "red"
            console.print(f"  [{status_color}]{client_name}: {report.status.value}[/{status_color}]")
            if report.warnings:
                for warning in report.warnings:
                    console.print(f"    - {warning}")
            if report.errors:
                for error in report.errors:
                    console.print(f"    - {error}")
        else:
            console.print(f"  [yellow]{client_name}: not detected[/yellow]")


@skills_app.command()
def inspect(
    skill_name: Optional[str] = typer.Option(None, "--skill", help="Inspect specific skill only"),
    client: Optional[str] = typer.Option(None, "--client", help="Check compatibility with specific client"),
) -> None:
    """Inspect skill compatibility with clients."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dirs = discover_skills(skills_dir)
    
    if skill_name:
        skill_dirs = [d for d in skill_dirs if d.name == skill_name]
        if not skill_dirs:
            console.print(f"[red]✗[/red] Skill not found: {skill_name}")
            raise typer.Exit(1)
    
    clients_to_check = [client] if client else list(SKILL_ADAPTERS.keys())
    
    for skill_dir in skill_dirs:
        console.print(f"\n[bold]{skill_dir.name}[/bold]")
        
        try:
            source = SkillSource(type="local", path=str(skill_dir))
            skill_def = load_skill_from_directory(skill_dir, source)
        except Exception as e:
            console.print(f"  [red]✗[/red] Failed to load: {e}")
            continue
        
        for client_name in clients_to_check:
            if client_name not in SKILL_ADAPTERS:
                console.print(f"  [red]✗[/red] Unknown client: {client_name}")
                continue
            
            adapter = SKILL_ADAPTERS[client_name]
            
            if not adapter.detect():
                console.print(f"  [yellow]{client_name}: not detected[/yellow]")
                continue
            
            report = adapter.inspect_compatibility(skill_def)
            
            status_color = "green" if report.is_compatible() else "yellow" if report.status.value == "requires-adaptation" else "red"
            console.print(f"  [{status_color}]{client_name}: {report.status.value}[/{status_color}]")
            
            if report.warnings:
                for warning in report.warnings:
                    console.print(f"    - {warning}")
            if report.errors:
                for error in report.errors:
                    console.print(f"    - {error}")


@skills_app.command()
def diff(
    client: str = typer.Argument(..., help="Client to check"),
    skill_name: Optional[str] = typer.Option(None, "--skill", help="Check specific skill only"),
) -> None:
    """Show planned skill changes without applying."""
    if client not in SKILL_ADAPTERS:
        console.print(f"[red]✗[/red] Unknown client: {client}")
        raise typer.Exit(1)
    
    adapter = SKILL_ADAPTERS[client]
    
    if not adapter.detect():
        console.print(f"[yellow]![/yellow] {client} not detected")
        raise typer.Exit(1)
    
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dirs = discover_skills(skills_dir)
    
    if skill_name:
        skill_dirs = [d for d in skill_dirs if d.name == skill_name]
        if not skill_dirs:
            console.print(f"[red]✗[/red] Skill not found: {skill_name}")
            raise typer.Exit(1)
    
    console.print(f"\n[bold]{client.upper()}[/bold]")
    locations = adapter.personal_skill_locations()
    if locations:
        console.print(f"  Skills location: {locations[0]}")
    else:
        console.print(f"  Skills location: N/A")
    console.print(f"  Symlink support: {adapter.supports_symlinks()}")
    
    for skill_dir in skill_dirs:
        try:
            source = SkillSource(type="local", path=str(skill_dir))
            skill_def = load_skill_from_directory(skill_dir, source)
        except Exception as e:
            console.print(f"  [red]✗[/red] {skill_dir.name}: Failed to load - {e}")
            continue
        
        # Check if skill is already installed
        if locations:
            client_skill_path = locations[0] / skill_dir.name
            if client_skill_path.exists():
                console.print(f"  [yellow]→[/yellow] {skill_dir.name}: Already installed")
            else:
                console.print(f"  [cyan]→[/cyan] {skill_dir.name}: Would be installed")
        else:
            console.print(f"  [yellow]→[/yellow] {skill_dir.name}: No skill location available")


@skills_app.command()
def apply(
    client: str = typer.Argument(..., help="Client to install skills to"),
    skill_name: Optional[str] = typer.Option(None, "--skill", help="Install specific skill only"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without applying"),
    yes: bool = typer.Option(False, "--yes", help="Apply without confirmation"),
) -> None:
    """Install skills to a client."""
    if client not in SKILL_ADAPTERS:
        console.print(f"[red]✗[/red] Unknown client: {client}")
        raise typer.Exit(1)
    
    adapter = SKILL_ADAPTERS[client]
    
    if not adapter.detect():
        console.print(f"[yellow]![/yellow] {client} not detected")
        raise typer.Exit(1)
    
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dirs = discover_skills(skills_dir)
    
    if skill_name:
        skill_dirs = [d for d in skill_dirs if d.name == skill_name]
        if not skill_dirs:
            console.print(f"[red]✗[/red] Skill not found: {skill_name}")
            raise typer.Exit(1)
    
    console.print(f"\n[bold]{client.upper()}[/bold]")
    locations = adapter.personal_skill_locations()
    if locations:
        console.print(f"  Skills location: {locations[0]}")
    else:
        console.print(f"  Skills location: N/A")
    console.print(f"  Symlink support: {adapter.supports_symlinks()}")
    
    installed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Map client to appropriate scope
    scope = "user" if client in ["claude", "copilot"] else "personal"
    
    for skill_dir in skill_dirs:
        try:
            source = SkillSource(type="local", path=str(skill_dir))
            skill_def = load_skill_from_directory(skill_dir, source)
        except Exception as e:
            console.print(f"  [red]✗[/red] {skill_dir.name}: Failed to load - {e}")
            error_count += 1
            continue
        
        # Check compatibility
        report = adapter.inspect_compatibility(skill_def)
        if not report.is_compatible():
            console.print(f"  [red]✗[/red] {skill_dir.name}: Incompatible")
            for warning in report.warnings:
                console.print(f"    - {warning}")
            for error in report.errors:
                console.print(f"    - {error}")
            error_count += 1
            continue
        
        # Check if already installed
        if locations:
            client_skill_path = locations[0] / skill_dir.name
            if client_skill_path.exists():
                console.print(f"  [yellow]→[/yellow] {skill_dir.name}: Already installed, skipping")
                skipped_count += 1
                continue
        
        # Install
        if dry_run:
            console.print(f"  [cyan]→[/cyan] {skill_dir.name}: Would install")
        else:
            if not yes:
                if not typer.confirm(f"Install '{skill_dir.name}' to {client}?"):
                    console.print(f"  Skipped")
                    skipped_count += 1
                    continue
            
            try:
                strategy = adapter.get_preferred_strategy()
                result = adapter.install(skill_def, scope, strategy)
                if result.success:
                    console.print(f"  [green]✓[/green] {skill_dir.name}: Installed ({result.strategy})")
                    installed_count += 1
                else:
                    console.print(f"  [red]✗[/red] {skill_dir.name}: Failed - {result.message}")
                    error_count += 1
            except Exception as e:
                console.print(f"  [red]✗[/red] {skill_dir.name}: Error - {e}")
                error_count += 1
    
    console.print(f"\nSummary: {installed_count} installed, {skipped_count} skipped, {error_count} error")
    
    if not dry_run and installed_count > 0:
        reload_instructions = adapter.reload_instructions()
        if reload_instructions:
            console.print(f"\n{reload_instructions}")
        else:
            console.print(f"\nReload {client} to use the newly installed skills.")


@skills_app.command()
def doctor(
    client: Optional[str] = typer.Option(None, "--client", help="Check specific client only"),
) -> None:
    """Check skill configuration and environment for issues."""
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    issues = []
    
    # Check if skills directory exists
    if not skills_dir.exists():
        issues.append(("error", f"Skills directory not found: {skills_dir}"))
    else:
        issues.append(("success", f"Skills directory exists: {skills_dir}"))
    
    # Check skills count
    skill_dirs = discover_skills(skills_dir)
    issues.append(("success", f"Found {len(skill_dirs)} skill(s)"))
    
    # Validate all skills
    results = validate_all_skills(skills_dir)
    valid_count = sum(1 for _, error in results if error is None)
    if valid_count == len(results):
        issues.append(("success", f"All {len(results)} skills are valid"))
    else:
        issues.append(("warning", f"{valid_count}/{len(results)} skills are valid"))
    
    # Check client detection
    clients_to_check = [client] if client else list(SKILL_ADAPTERS.keys())
    for client_name in clients_to_check:
        if client_name not in SKILL_ADAPTERS:
            issues.append(("error", f"Unknown client: {client_name}"))
            continue
        
        adapter = SKILL_ADAPTERS[client_name]
        if adapter.detect():
            issues.append(("success", f"{client_name} detected"))
            locations = adapter.personal_skill_locations()
            if locations:
                issues.append(("success", f"{client_name} skills location: {locations[0]}"))
            else:
                issues.append(("warning", f"{client_name} has no skill locations"))
            issues.append(("success", f"{client_name} symlink support: {adapter.supports_symlinks()}"))
        else:
            issues.append(("warning", f"{client_name} not detected"))
    
    # Output results
    for level, message in issues:
        if level == "error":
            console.print(f"[red]✗[/red] {message}")
        elif level == "warning":
            console.print(f"[yellow]![/yellow] {message}")
        else:
            console.print(f"[green]✓[/green] {message}")


@skills_app.command()
def remove(
    skill_name: str,
    client: str = typer.Argument(..., help="Client to remove skill from"),
    yes: bool = typer.Option(False, "--yes", help="Remove without confirmation"),
) -> None:
    """Remove a skill from a client."""
    if client not in SKILL_ADAPTERS:
        console.print(f"[red]✗[/red] Unknown client: {client}")
        raise typer.Exit(1)
    
    adapter = SKILL_ADAPTERS[client]
    
    if not adapter.detect():
        console.print(f"[yellow]![/yellow] {client} not detected")
        raise typer.Exit(1)
    
    ensure_skills_dir()
    skills_dir = get_skills_dir()
    
    skill_dir = skills_dir / skill_name
    if not skill_dir.exists():
        console.print(f"[red]✗[/red] Skill not found in canonical store: {skill_name}")
        raise typer.Exit(1)
    
    try:
        source = SkillSource(type="local", path=str(skill_dir))
        skill_def = load_skill_from_directory(skill_dir, source)
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to load skill: {e}")
        raise typer.Exit(1)
    
    console.print(f"\n[bold]{client.upper()}[/bold]")
    
    if not yes:
        if not typer.confirm(f"Remove '{skill_name}' from {client}?"):
            console.print("Cancelled")
            return
    
    try:
        result = adapter.uninstall(skill_name, "personal")
        if result.success:
            console.print(f"[green]✓[/green] Skill removed from {client}")
        else:
            console.print(f"[red]✗[/red] Failed to remove: {result.message}")
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@app.callback()
def version_callback(
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    """Show version and exit."""
    if version:
        console.print(f"agent-sync {__version__}")
        raise typer.Exit()


if __name__ == "__main__":
    app()
