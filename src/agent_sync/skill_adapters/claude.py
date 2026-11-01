"""Claude Code skill adapter for Agent Skills synchronization."""

from pathlib import Path
from typing import Literal

from agent_sync.models import SkillDefinition
from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)


class ClaudeSkillAdapter(SkillAdapter):
    """Adapter for synchronizing skills to Claude Code."""

    def __init__(self):
        self._name = "claude"

    @property
    def name(self) -> str:
        return self._name

    def detect(self) -> bool:
        """Check if Claude Code is installed."""
        claude_config = Path.home() / ".claude.json"
        return claude_config.exists()

    def personal_skill_locations(self) -> list[Path]:
        """Return Claude Code personal skill locations."""
        return [Path.home() / ".claude" / "skills"]

    def project_skill_locations(self, project_root: Path) -> list[Path]:
        """Return Claude Code project skill locations."""
        return [project_root / ".claude" / "skills"]

    def supports_symlinks(self) -> bool:
        """Claude Code symlink support is unknown - assume yes for now."""
        return True

    def inspect_compatibility(self, skill: SkillDefinition) -> CompatibilityReport:
        """Check skill compatibility with Claude Code."""
        warnings = []
        errors = []

        # Claude Code supports Agent Skills spec with extensions
        # Check for Claude-specific extensions that might not be portable
        # - disable-model-invocation (Claude-specific)
        # - allowed-tools (works in CLI but not SDK)
        # - arguments (Claude-specific)

        # Check description length (Claude.ai limit is 200 chars, spec allows 1024)
        if len(skill.description) > 200:
            warnings.append(
                f"Description is {len(skill.description)} characters; Claude.ai limit is 200. "
                "If uploading to Claude.ai, description will be truncated."
            )

        # Check name length (spec limit is 64 chars)
        if len(skill.name) > 64:
            errors.append(
                f"Name is {len(skill.name)} characters; Agent Skills spec limit is 64. "
                "Will be rejected."
            )

        if errors:
            return CompatibilityReport(
                status=CompatibilityStatus.UNSUPPORTED, warnings=warnings, errors=errors
            )

        if warnings:
            return CompatibilityReport(
                status=CompatibilityStatus.COMPATIBLE_WITH_WARNINGS, warnings=warnings, errors=errors
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
        """Install skill for Claude Code."""
        if scope not in ["user", "project"]:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message=f"Invalid scope: {scope}. Claude Code supports 'user' and 'project' scopes.",
                warnings=[],
            )

        # Determine destination based on scope
        if scope == "user":
            dest_dir = Path.home() / ".claude" / "skills"
        else:
            # For project scope, we need a project root - this should be passed separately
            # For now, assume user scope
            dest_dir = Path.home() / ".claude" / "skills"

        dest_path = dest_dir / skill.name

        if strategy == "native":
            # For native strategy, the skill should already be in Claude location
            # This would require Claude Code to read from ~/.agents/skills
            # Claude Code doesn't natively support this, so native is not available
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="Claude Code does not natively read from ~/.agents/skills. Use 'symlink' or 'copy' strategy.",
                warnings=[],
            )

        if strategy == "symlink":
            if not self.supports_symlinks():
                return InstallResult(
                    success=False,
                    strategy="unsupported",
                    destination=None,
                    message="Symlinks not supported for Claude Code.",
                    warnings=[],
                )

            # Create symlink from canonical location to Claude location
            canonical_path = Path.home() / ".agents" / "skills" / skill.name
            if not canonical_path.exists():
                return InstallResult(
                    success=False,
                    strategy="symlink",
                    destination=str(dest_path),
                    message=f"Canonical skill not found: {canonical_path}",
                    warnings=[],
                )

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
            # Copy strategy would copy from canonical store to Claude location
            # This is not implemented yet
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message="Copy strategy not yet implemented for Claude Code.",
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
        """Remove skill from Claude Code."""
        if scope not in ["user", "project"]:
            return InstallResult(
                success=False,
                strategy="unsupported",
                destination=None,
                message=f"Invalid scope: {scope}. Claude Code supports 'user' and 'project' scopes.",
                warnings=[],
            )

        if scope == "user":
            skill_path = Path.home() / ".claude" / "skills" / skill_name
        else:
            # For project scope, we need project root
            skill_path = Path.home() / ".claude" / "skills" / skill_name

        if not skill_path.exists():
            return InstallResult(
                success=True,
                strategy="symlink",
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
        """Return instructions for reloading Claude Code skills."""
        return "Restart Claude Code to load new skills."
