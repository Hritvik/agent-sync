"""Cursor skill adapter for Agent Skills synchronization."""

from pathlib import Path
from typing import Literal

from agent_sync.models import SkillDefinition, SkillSource
from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)


class CursorSkillAdapter(SkillAdapter):
    """Adapter for synchronizing skills to Cursor."""

    def __init__(self):
        self._name = "cursor"

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> bool:
        """Check if Cursor is installed."""
        cursor_config = Path.home() / ".cursor"
        return cursor_config.exists()

    def personal_skill_locations(self) -> list[Path]:
        """Return Cursor personal skill locations."""
        # Cursor is based on VS Code, similar structure to Claude Code
        return [Path.home() / ".cursor" / "skills"]

    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return Cursor project skill locations."""
        # Cursor doesn't explicitly document project-level skills
        return []

    def supports_symlinks(self) -> bool:
        """Cursor should support symlinks like other VS Code-based editors."""
        return True

    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Check skill compatibility with Cursor."""
        warnings = []
        errors = []

        # Cursor is based on VS Code, so it should be compatible with most skills
        # Check for Cursor-specific extensions that might not be portable
        # (None documented in research)

        if not warnings and not errors:
            return CompatibilityReport(
                status=CompatibilityStatus.COMPATIBLE,
                warnings=[],
                errors=[],
            )

        return CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS if warnings else CompatibilityStatus.COMPATIBLE,
            warnings=warnings,
            errors=errors,
        )

    def install(
        self,
        skill: SkillDefinition,
        scope: str,
        strategy: str,
    ) -> InstallResult:
        """Expose the canonical skill to Cursor."""
        locations = self.personal_skill_locations()
        if not locations:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="No skill location available for Cursor",
                warnings=[],
            )

        skills_dir = locations[0]
        skill_dir = skills_dir / skill.name

        # Create skills directory if it doesn't exist
        skills_dir.mkdir(parents=True, exist_ok=True)

        # Remove existing installation
        if skill_dir.exists():
            if skill_dir.is_symlink() or skill_dir.is_dir():
                import shutil

                shutil.rmtree(skill_dir)

        # Install based on strategy
        if strategy == "symlink" and self.supports_symlinks():
            # Symlink to canonical skill
            canonical_path = Path(skill.source.path) if skill.source.path else None
            if not canonical_path or not canonical_path.exists():
                return InstallResult(
                    success=False,
                    strategy="symlink",
                    destination=str(skill_dir),
                    message="Canonical skill path not available for symlinking",
                    warnings=[],
                )

            skill_dir.symlink_to(canonical_path)
            return InstallResult(
                success=True,
                strategy="symlink",
                destination=str(skill_dir),
                message="Skill symlinked to Cursor",
                warnings=[],
            )
        elif strategy == "copy":
            # Copy skill directory
            canonical_path = Path(skill.source.path) if skill.source.path else None
            if not canonical_path or not canonical_path.exists():
                return InstallResult(
                    success=False,
                    strategy="copy",
                    destination=str(skill_dir),
                    message="Canonical skill path not available for copying",
                    warnings=[],
                )

            import shutil

            shutil.copytree(canonical_path, skill_dir)
            return InstallResult(
                success=True,
                strategy="copy",
                destination=str(skill_dir),
                message="Skill copied to Cursor",
                warnings=[],
            )
        else:
            return InstallResult(
                success=False,
                strategy=strategy,
                destination=None,
                message=f"Strategy '{strategy}' not supported for Cursor",
                warnings=[],
            )

    def uninstall(self, skill_name: str, scope: str) -> InstallResult:
        """Remove only the managed link or copy."""
        locations = self.personal_skill_locations()
        if not locations:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="No skill location available for Cursor",
                warnings=[],
            )

        skills_dir = locations[0]
        skill_dir = skills_dir / skill_name

        if not skill_dir.exists():
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=str(skill_dir),
                message="Skill not installed in Cursor",
                warnings=[],
            )

        # Remove the skill directory
        import shutil

        shutil.rmtree(skill_dir)

        return InstallResult(
            success=True,
            strategy="remove",
            destination=str(skill_dir),
            message="Skill removed from Cursor",
            warnings=[],
        )

    def reload_instructions(self) -> str | None:
        """Describe how to make Cursor notice changes."""
        return "Restart Cursor to load new skills."
