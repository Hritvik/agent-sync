"""Pydantic models for the canonical MCP registry and Agent Skills store."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TransportType(str, Enum):
    """Supported MCP transport types."""

    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"
    WS = "ws"


class EnvValueSource(BaseModel):
    """Environment variable value source."""

    from_env: str = Field(..., description="Name of environment variable to read from")


class EnvValueLiteral(BaseModel):
    """Literal environment variable value."""

    value: str = Field(..., description="Literal value to use")


EnvValue = EnvValueSource | EnvValueLiteral


class StdioServerConfig(BaseModel):
    """Configuration for stdio MCP servers."""

    transport: Literal[TransportType.STDIO] = TransportType.STDIO
    command: str = Field(..., description="Command to start the server")
    args: list[str] = Field(default_factory=list, description="Arguments to pass to the command")
    cwd: str | None = Field(None, description="Working directory for the server")
    env: dict[str, EnvValue] = Field(default_factory=dict, description="Environment variables")


class HttpServerConfig(BaseModel):
    """Configuration for HTTP MCP servers."""

    transport: Literal[TransportType.HTTP] = TransportType.HTTP
    url: str = Field(..., description="URL of the MCP server")
    headers: dict[str, EnvValue] = Field(default_factory=dict, description="HTTP headers")


class SseServerConfig(BaseModel):
    """Configuration for SSE MCP servers."""

    transport: Literal[TransportType.SSE] = TransportType.SSE
    url: str = Field(..., description="URL of the MCP server")
    headers: dict[str, EnvValue] = Field(default_factory=dict, description="HTTP headers")


class WsServerConfig(BaseModel):
    """Configuration for WebSocket MCP servers."""

    transport: Literal[TransportType.WS] = TransportType.WS
    url: str = Field(..., description="WebSocket URL of the MCP server")
    headers: dict[str, EnvValue] = Field(default_factory=dict, description="HTTP headers")


ServerConfig = StdioServerConfig | HttpServerConfig | SseServerConfig | WsServerConfig


class ClientFilter(BaseModel):
    """Client inclusion/exclusion filter for a server."""

    include: list[str] | None = Field(None, description="List of clients to include this server in")
    exclude: list[str] | None = Field(None, description="List of clients to exclude this server from")


class ServerMetadata(BaseModel):
    """Optional metadata for a server."""

    homepage: str | None = Field(None, description="Homepage URL for the server")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class ServerDefinition(BaseModel):
    """Definition of a single MCP server in the canonical registry."""

    description: str = Field(..., description="Human-readable description of the server")
    transport: TransportType = Field(..., description="Transport type")
    config: ServerConfig = Field(..., description="Server-specific configuration")
    enabled: bool = Field(True, description="Whether the server is enabled")
    clients: ClientFilter = Field(default_factory=ClientFilter, description="Client filter")
    metadata: ServerMetadata = Field(default_factory=ServerMetadata, description="Optional metadata")

    @model_validator(mode="after")
    def validate_transport_config_match(self) -> "ServerDefinition":
        """Ensure the transport type matches the config type."""
        if self.transport == TransportType.STDIO and not isinstance(self.config, StdioServerConfig):
            raise ValueError("Transport 'stdio' requires StdioServerConfig")
        if self.transport == TransportType.HTTP and not isinstance(self.config, HttpServerConfig):
            raise ValueError("Transport 'http' requires HttpServerConfig")
        if self.transport == TransportType.SSE and not isinstance(self.config, SseServerConfig):
            raise ValueError("Transport 'sse' requires SseServerConfig")
        if self.transport == TransportType.WS and not isinstance(self.config, WsServerConfig):
            raise ValueError("Transport 'ws' requires WsServerConfig")
        return self


class DefaultsConfig(BaseModel):
    """Default values for server definitions."""

    enabled: bool = Field(True, description="Default enabled state for servers")


class Registry(BaseModel):
    """Canonical MCP server registry."""

    version: int = Field(1, description="Registry format version")
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig, description="Default values")
    servers: dict[str, ServerDefinition] = Field(default_factory=dict, description="Server definitions")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        """Validate the registry version."""
        if v != 1:
            raise ValueError(f"Unsupported registry version: {v}. Only version 1 is supported.")
        return v


class ProfileServerList(BaseModel):
    """List of servers in a profile."""

    servers: list[str] = Field(..., description="List of server names to include")


class ProfileDefinition(BaseModel):
    """Definition of a profile."""

    servers: list[str] = Field(..., description="List of server names to include")


class Profiles(BaseModel):
    """Profile definitions."""

    profiles: dict[str, ProfileDefinition] = Field(default_factory=dict, description="Profile definitions")


class ClientState(BaseModel):
    """State tracking for a single client."""

    config_path: str = Field(..., description="Path to the client's config file")
    managed_servers: dict[str, str] = Field(
        default_factory=dict, description="Server names and their config hashes"
    )
    last_applied: str | None = Field(None, description="ISO timestamp of last application")
    mcp_sync_version: str | None = Field(None, description="Version of mcp-sync that last applied")


class State(BaseModel):
    """State tracking for managed servers across clients."""

    clients: dict[str, ClientState] = Field(default_factory=dict, description="Client-specific state")


# ============================================================================
# Agent Skills Models
# ============================================================================

class SkillSource(BaseModel):
    """Source information for a skill."""

    type: Literal["local", "git", "github", "archive", "client"] = Field(..., description="Source type")
    path: str | None = Field(None, description="Local path for local sources")
    repository: str | None = Field(None, description="Git repository URL")
    commit: str | None = Field(None, description="Git commit hash or tag")
    client: str | None = Field(None, description="Client name for client-imported skills")


class SkillMetadata(BaseModel):
    """Metadata for a skill."""

    author: str | None = Field(None, description="Skill author")
    version: str | None = Field(None, description="Skill version")
    license: str | None = Field(None, description="License information")
    homepage: str | None = Field(None, description="Homepage URL")
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")


class SkillDefinition(BaseModel):
    """Definition of a single skill in the canonical store."""

    name: str = Field(..., description="Skill name (must match directory name)")
    description: str = Field(..., description="Skill description")
    source: SkillSource = Field(..., description="Source information")
    enabled: bool = Field(True, description="Whether the skill is enabled")
    metadata: SkillMetadata = Field(default_factory=SkillMetadata, description="Optional metadata")
    trust_state: Literal["unreviewed", "trusted", "blocked", "modified-after-review"] = Field(
        "unreviewed", description="Trust state of the skill"
    )
    content_hash: str | None = Field(None, description="SHA256 hash of skill content")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate skill name matches Agent Skills spec."""
        if not v:
            raise ValueError("Skill name cannot be empty")
        if len(v) > 64:
            raise ValueError("Skill name must be 64 characters or less")
        # Check for valid characters (lowercase, numbers, hyphens)
        if not all(c.islower() or c.isdigit() or c == "-" for c in v):
            raise ValueError("Skill name must contain only lowercase letters, numbers, and hyphens")
        if v.startswith("-") or v.endswith("-"):
            raise ValueError("Skill name cannot start or end with a hyphen")
        if "--" in v:
            raise ValueError("Skill name cannot contain consecutive hyphens")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate skill description."""
        if not v:
            raise ValueError("Skill description cannot be empty")
        if len(v) > 1024:
            raise ValueError("Skill description must be 1024 characters or less")
        return v


class SkillDefaultsConfig(BaseModel):
    """Default values for skill definitions."""

    enabled: bool = Field(True, description="Default enabled state for skills")
    trust_state: Literal["unreviewed", "trusted", "blocked", "modified-after-review"] = Field(
        "unreviewed", description="Default trust state"
    )


class SkillRegistry(BaseModel):
    """Canonical Agent Skills registry."""

    version: int = Field(1, description="Registry format version")
    defaults: SkillDefaultsConfig = Field(default_factory=SkillDefaultsConfig, description="Default values")
    skills: dict[str, SkillDefinition] = Field(default_factory=dict, description="Skill definitions")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: int) -> int:
        """Validate the registry version."""
        if v != 1:
            raise ValueError(f"Unsupported registry version: {v}. Only version 1 is supported.")
        return v


class SkillClientState(BaseModel):
    """State tracking for a skill on a specific client."""

    strategy: Literal["native", "symlink", "copy", "external-directory", "unsupported"] = Field(
        ..., description="Installation strategy used"
    )
    destination: str | None = Field(None, description="Destination path for symlink/copy strategies")
    last_applied: str | None = Field(None, description="ISO timestamp of last application")
    content_hash: str | None = Field(None, description="Hash of skill content at time of application")


class SkillState(BaseModel):
    """State tracking for managed skills across clients."""

    skills: dict[str, dict[str, SkillClientState]] = Field(
        default_factory=dict, description="Skill name -> client -> state"
    )
