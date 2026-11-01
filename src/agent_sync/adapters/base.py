"""Base adapter interface for MCP client configuration."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol

from agent_sync.models import Registry


class ClientAdapter(Protocol):
    """Protocol for MCP client configuration adapters."""

    name: str

    def detect(self) -> bool:
        """Return whether the client appears to be installed."""
        ...

    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for this client."""
        ...

    def load_config(self, scope: str = "user") -> dict:
        """Read and parse the existing client configuration."""
        ...

    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to the client-specific schema."""
        ...

    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge managed MCP entries while preserving unrelated settings."""
        ...

    def validate_support(self, registry: Registry) -> list[str]:
        """Return warnings for unsupported features or transports."""
        ...

    def write_config(self, config: dict, scope: str = "user") -> None:
        """Safely write the final configuration."""
        ...


class BaseAdapter(ABC):
    """Base class for MCP client adapters with common functionality."""

    name: str

    def __init__(self) -> None:
        """Initialize the adapter."""
        self._config_cache: dict[str, dict] = {}

    @abstractmethod
    def detect(self) -> bool:
        """Return whether the client appears to be installed."""
        pass

    @abstractmethod
    def config_path(self, scope: str = "user") -> Path:
        """Return the configuration path for this client."""
        pass

    @abstractmethod
    def load_config(self, scope: str = "user") -> dict:
        """Read and parse the existing client configuration."""
        pass

    @abstractmethod
    def render_servers(self, registry: Registry, scope: str = "user") -> dict:
        """Convert canonical servers to the client-specific schema."""
        pass

    @abstractmethod
    def merge_config(
        self,
        existing: dict,
        generated: dict,
        scope: str = "user",
    ) -> dict:
        """Merge managed MCP entries while preserving unrelated settings."""
        pass

    @abstractmethod
    def validate_support(self, registry: Registry) -> list[str]:
        """Return warnings for unsupported features or transports."""
        pass

    @abstractmethod
    def write_config(self, config: dict, scope: str = "user") -> None:
        """Safely write the final configuration."""
        pass

    def _cache_config(self, scope: str, config: dict) -> None:
        """Cache the loaded configuration."""
        self._config_cache[scope] = config

    def _get_cached_config(self, scope: str) -> dict | None:
        """Get the cached configuration if available."""
        return self._config_cache.get(scope)

    def _clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._config_cache.clear()
