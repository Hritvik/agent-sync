"""Base adapter protocol for Agent Skills synchronization."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Literal

from agent_sync.models import SkillDefinition


class CompatibilityStatus(str, Enum):
    """Compatibility status for a skill with a client."""

    COMPATIBLE = "compatible"
    COMPATIBLE_WITH_WARNINGS = "compatible-with-warnings"
    REQUIRES_ADAPTATION = "requires-adaptation"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


@dataclass
class CompatibilityReport:
    """Report on skill compatibility with a client."""

    status: CompatibilityStatus
    warnings: list[str]
    errors: list[str]

    def is_compatible(self) -> bool:
        """Check if skill is compatible (may have warnings)."""
        return self.status in [CompatibilityStatus.COMPATIBLE, CompatibilityStatus.COMPATIBLE_WITH_WARNINGS]

    def has_issues(self) -> bool:
        """Check if skill has any issues."""
        return bool(self.warnings or self.errors)


@dataclass
class InstallResult:
    """Result of installing a skill for a client."""

    success: bool
    strategy: Literal["native", "symlink", "copy", "external-directory", "unsupported"]
    destination: str | None
    message: str
    warnings: list[str]


class SkillAdapter(ABC):
    """Base adapter for synchronizing skills to a specific client."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the client name."""
        pass

    @abstractmethod
    def detect(self) -> bool:
        """Return whether the agent is installed."""
        pass

    @abstractmethod
    def personal_skill_locations(self) -> list[Path]:
        """Return supported personal skill locations."""
        pass

    @abstractmethod
    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return supported project skill locations."""
        pass

    @abstractmethod
    def supports_symlinks(self) -> bool:
        """Return whether symlinked skill directories are supported."""
        pass

    @abstractmethod
    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Report unsupported or agent-specific skill features."""
        pass

    @abstractmethod
    def install(
        self,
        skill: SkillDefinition,
        scope: str,
        strategy: str,
    ) -> InstallResult:
        """Expose the canonical skill to the agent."""
        pass

    @abstractmethod
    def uninstall(self, skill_name: str, scope: str) -> InstallResult:
        """Remove only the managed link or copy."""
        pass

    @abstractmethod
    def reload_instructions(self) -> str | None:
        """Describe how to make the client notice changes."""
        pass

    def get_preferred_strategy(self) -> str:
        """Return the preferred installation strategy for this client."""
        if self.supports_symlinks():
            return "symlink"
        return "copy"
