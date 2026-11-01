"""Codex skill adapter for Agent Skills synchronization."""

import re
from pathlib import Path

from agent_sync.models import SkillDefinition
from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)


class CodexSkillAdapter(SkillAdapter):
    """Adapter for synchronizing skills to Codex."""

    def __init__(self):
        self._name = "codex"

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> bool:
        """Check if Codex is installed."""
        codex_config = Path.home() / ".codex" / "config.toml"
        return codex_config.exists()

    def personal_skill_locations(self) -> list[Path]:
        """Return Codex personal skill locations."""
        return [Path.home() / ".agents" / "skills", Path.home() / ".codex" / "skills"]

    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return Codex project skill locations."""
        return [project_root / ".agents" / "skills"]

    def supports_symlinks(self) -> bool:
        """Codex follows symlinked skill folders."""
        return True

    def get_preferred_strategy(self) -> str:
        """The canonical shared store is already a Codex discovery location."""
        return "native"

    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Check skill compatibility with Codex."""
        warnings = []
        errors = []

        # These are agent-sync's portable format constraints, not host limits.
        if len(skill.description) > 1024:
            errors.append("Description exceeds agent-sync's portable 1024-character maximum.")
        if len(skill.name) > 64:
            errors.append("Name exceeds agent-sync's portable 64-character maximum.")

        if errors:
            return CompatibilityReport(
                status=CompatibilityStatus.UNSUPPORTED, warnings=warnings, errors=errors
            )

        return CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE, warnings=warnings, errors=errors
        )

    @staticmethod
    def _result(
        success: bool, strategy: str, destination: Path | None, message: str
    ) -> InstallResult:
        return InstallResult(
            success=success,
            strategy=strategy,
            destination=str(destination) if destination else None,
            message=message,
            warnings=[],
        )

    def _locations(self, scope: str) -> list[Path]:
        if scope in {"user", "personal"}:
            return self.personal_skill_locations()
        if scope == "project":
            return self.project_skill_locations(Path.cwd())
        return []

    def install(self, skill: SkillDefinition, scope: str, strategy: str) -> InstallResult:
        """Expose a local skill without overwriting an existing installation.

        Project scope is relative to the invoking process's working directory.
        Native mode verifies discovery; symlink mode links the provided source.
        """
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill.name):
            return self._result(False, "unsupported", None, "Invalid skill name.")
        locations = self._locations(scope)
        if not locations:
            return self._result(False, "unsupported", None, f"Invalid scope: {scope}")
        if strategy not in {"native", "symlink"}:
            return self._result(False, "unsupported", None, f"Unsupported strategy: {strategy}")
        source = Path(skill.source.path).expanduser() if skill.source.path else None
        if source is None or not (source / "SKILL.md").is_file():
            return self._result(False, strategy, None, "Local skill source with SKILL.md required.")
        if strategy == "native":
            for location in locations:
                candidate = location / skill.name
                if (candidate / "SKILL.md").is_file() and candidate.resolve() == source.resolve():
                    return self._result(
                        True, strategy, candidate, "Skill is already discoverable by Codex."
                    )
            return self._result(
                False,
                strategy,
                source,
                "Source is outside this scope's discovery locations; use symlink strategy.",
            )
        destination = locations[0] / skill.name
        if destination.exists() or destination.is_symlink():
            if destination.resolve() == source.resolve() and (destination / "SKILL.md").is_file():
                return self._result(
                    True, strategy, destination, "Skill already points to this source."
                )
            return self._result(
                False, strategy, destination, "Destination already exists; preserved unchanged."
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source.resolve(), target_is_directory=True)
        return self._result(True, strategy, destination, "Created skill symlink.")

    def uninstall(self, skill_name: str, scope: str) -> InstallResult:
        """Preserve shared source content when installation ownership is unknown.

        The adapter API does not carry per-install ownership state. Even a symlink
        in the shared store can belong to another client or installation owner.
        """
        if not skill_name or skill_name in {".", ".."} or any(c in skill_name for c in "/\\"):
            return self._result(False, "unsupported", None, "Invalid skill name.")
        locations = self._locations(scope)
        if not locations:
            return self._result(False, "unsupported", None, f"Invalid scope: {scope}")
        for location in locations:
            destination = location / skill_name
            if destination.exists() or destination.is_symlink():
                return self._result(
                    False,
                    "native",
                    destination,
                    "Preserved skill: ownership is not tracked. Disable its exact SKILL.md "
                    "path using [[skills.config]] in Codex config.toml instead.",
                )
        return self._result(
            True, "native", locations[0] / skill_name, "Skill not found (already absent)."
        )

    def reload_instructions(self) -> str | None:
        """Describe refresh behavior without requiring a restart on every edit."""
        return "Codex detects skill changes automatically; restart if changes do not appear."
