"""GitHub Copilot skill adapter for Agent Skills synchronization."""

from pathlib import Path
from typing import Literal

from agent_sync.models import SkillDefinition
from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)


class CopilotSkillAdapter(SkillAdapter):
    """Adapter for synchronizing skills to GitHub Copilot."""

    def __init__(self):
        self._name = "copilot"

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> bool:
        """Check if GitHub Copilot is installed."""
        # Check for Copilot CLI or VS Code with Copilot
        copilot_config = Path.home() / ".copilot"
        return copilot_config.exists()

    def personal_skill_locations(self) -> list[Path]:
        """Return GitHub Copilot personal skill locations."""
        return [
            Path.home() / ".copilot" / "skills",
            Path.home() / ".agents" / "skills",  # Canonical location
        ]

    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return GitHub Copilot project skill locations."""
        return [
            project_root / ".github" / "skills",
            project_root / ".claude" / "skills",
            project_root / ".agents" / "skills",
        ]

    def supports_symlinks(self) -> bool:
        """GitHub Copilot symlink support is unknown - assume yes for now."""
        return True

    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Check skill compatibility with GitHub Copilot."""
        warnings = []
        errors = []

        # GitHub Copilot follows the Agent Skills specification
        # Check for any Copilot-specific extensions
        # (None documented in research)

        # Check name length (spec limit is 64 chars)
        if len(skill.name) > 64:
            errors.append(
                f"Name is {len(skill.name)} characters; Agent Skills spec limit is 64. "
                "Will be rejected."
            )

        # Check description length (spec allows 1024 chars)
        if len(skill.description) > 1024:
            errors.append(
                f"Description is {len(skill.description)} characters; Agent Skills spec limit is 1024. "
                "Will be rejected."
            )

        if errors:
            return CompatibilityReport(
                status=CompatibilityStatus.UNSUPPORTED, warnings=warnings, errors=errors
            )

        return CompatibilityReport(
            status=CompatibilityStatus.COMPATIBLE, warnings=warnings, errors=errors
        )

    def install(
        self,
        skill: SkillDefinition,
        scope: str,
        strategy: str,
    ) -> InstallResult:
        """Install skill for GitHub Copilot."""
        if scope not in ["user", "project"]:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message=f"Invalid scope: {scope}. GitHub Copilot supports 'user' and 'project' scopes.",
                warnings=[],
            )

        # GitHub Copilot natively supports ~/.agents/skills
        if strategy == "native":
            # For native strategy, the skill should already be in canonical location
            canonical_path = Path.home() / ".agents" / "skills" / skill.name
            if not canonical_path.exists():
                return InstallResult(
                    success=False,
                    strategy="native",
                    destination=str(canonical_path),
                    message=f"Canonical skill not found: {canonical_path}",
                    warnings=[],
                )

            return InstallResult(
                success=True,
                strategy="native",
                destination=str(canonical_path),
                message="Skill already in canonical location (native strategy). GitHub Copilot will discover it automatically.",
                warnings=[],
            )

        if strategy == "symlink":
            if not self.supports_symlinks():
                return InstallResult(
                    success=False,
                    strategy="unsupported",
                    destination=None,
                    message="Symlinks not supported for GitHub Copilot.",
                    warnings=[],
                )

            # Create symlink from canonical location to Copilot location
            canonical_path = Path.home() / ".agents" / "skills" / skill.name
            if not canonical_path.exists():
                return InstallResult(
                    success=False,
                    strategy="symlink",
                    destination=None,
                    message=f"Canonical skill not found: {canonical_path}",
                    warnings=[],
                )

            # Determine destination based on scope
            if scope == "user":
                dest_dir = Path.home() / ".copilot" / "skills"
            else:
                # For project scope, we need a project root
                dest_dir = Path.home() / ".copilot" / "skills"

            dest_path = dest_dir / skill.name

            if dest_path.exists():
                if dest_path.is_symlink() and dest_path.resolve() == canonical_path:
                    return InstallResult(
                        success=True,
                        strategy="symlink",
                        destination=str(dest_path),
                        message="Symlink already exists and points to canonical location.",
                        warnings=[],
                    )
                return InstallResult(
                    success=False,
                    strategy="symlink",
                    destination=str(dest_path),
                    message=f"Destination already exists: {dest_path}",
                    warnings=[],
                )

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path.symlink_to(canonical_path)
            return InstallResult(
                success=True,
                strategy="symlink",
                destination=str(dest_path),
                message=f"Created symlink from {dest_path} to {canonical_path}",
                warnings=[],
            )

        if strategy == "copy":
            # Copy strategy would copy from canonical store to Copilot location
            # This is not implemented yet
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="Copy strategy not yet implemented for GitHub Copilot.",
                warnings=[],
            )

        return InstallResult(
            success=False,
            strategy="unsupported",
            destination=None,
            message=f"Unsupported strategy: {strategy}",
            warnings=[],
        )

    def uninstall(self, skill_name: str, scope: str) -> InstallResult:
        """Remove skill from GitHub Copilot."""
        if scope not in ["user", "project"]:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message=f"Invalid scope: {scope}. GitHub Copilot supports 'user' and 'project' scopes.",
                warnings=[],
            )

        # For native strategy, we don't remove from canonical location
        # For symlink/copy, we remove from Copilot location
        if scope == "user":
            skill_path = Path.home() / ".copilot" / "skills" / skill_name
        else:
            skill_path = Path.home() / ".copilot" / "skills" / skill_name

        if not skill_path.exists():
            return InstallResult(
                success=True,
                strategy="native",
                destination=str(skill_path),
                message="Skill not found (already removed).",
                warnings=[],
            )

        # Remove the symlink or directory
        if skill_path.is_symlink():
            skill_path.unlink()
        else:
            import shutil

            shutil.rmtree(skill_path)

        return InstallResult(
            success=True,
            strategy="symlink",
            destination=str(skill_path),
            message=f"Removed skill from {skill_path}",
            warnings=[],
        )

    def reload_instructions(self) -> str | None:
        """Return instructions for reloading GitHub Copilot skills."""
        return "Restart GitHub Copilot to load new skills."
