"""Antigravity skill adapter for Agent Skills synchronization."""

from pathlib import Path
from typing import Literal

from agent_sync.models import SkillDefinition, SkillSource
from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)


class AntigravitySkillAdapter(SkillAdapter):
    """Adapter for synchronizing skills to Antigravity."""

    def __init__(self):
        self._name = "antigravity"

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> bool:
        """Check if Antigravity is installed."""
        antigravity_config = Path.home() / ".antigravity"
        return antigravity_config.exists()

    def personal_skill_locations(self) -> list[Path]:
        """Return Antigravity personal skill locations."""
        # Antigravity configuration structure
        return [Path.home() / ".antigravity" / "skills"]

    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return Antigravity project skill locations."""
        # Antigravity doesn't explicitly document project-level skills
        return []

    def supports_symlinks(self) -> bool:
        """Antigravity should support symlinks like other AI coding environments."""
        return True

    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Check skill compatibility with Antigravity."""
        warnings = []
        errors = []

        # Antigravity should be compatible with most skills
        # Check for Antigravity-specific extensions that might not be portable
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
        """Expose the canonical skill to Antigravity."""
        locations = self.personal_skill_locations()
        if not locations:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="No skill location available for Antigravity",
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
                message="Skill symlinked to Antigravity",
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
                message="Skill copied to Antigravity",
                warnings=[],
            )
        else:
            return InstallResult(
                success=False,
                strategy=strategy,
                destination=None,
                message=f"Strategy '{strategy}' not supported for Antigravity",
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
                message="No skill location available for Antigravity",
                warnings=[],
            )

        skills_dir = locations[0]
        skill_dir = skills_dir / skill_name

        if not skill_dir.exists():
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=str(skill_dir),
                message="Skill not installed in Antigravity",
                warnings=[],
            )

        # Remove the skill directory
        import shutil

        shutil.rmtree(skill_dir)

        return InstallResult(
            success=True,
            strategy="remove",
            destination=str(skill_dir),
            message="Skill removed from Antigravity",
            warnings=[],
        )

    def reload_instructions(self) -> str | None:
        """Describe how to make Antigravity notice changes."""
        return "Restart Antigravity to load new skills."
