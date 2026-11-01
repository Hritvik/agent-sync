"""Skill adapters for synchronizing Agent Skills to different clients."""

from agent_sync.skill_adapters.base import (
    CompatibilityReport,
    CompatibilityStatus,
    InstallResult,
    SkillAdapter,
)
from agent_sync.skill_adapters.antigravity import AntigravitySkillAdapter
from agent_sync.skill_adapters.claude import ClaudeSkillAdapter
from agent_sync.skill_adapters.codex import CodexSkillAdapter
from agent_sync.skill_adapters.copilot import CopilotSkillAdapter
from agent_sync.skill_adapters.cursor import CursorSkillAdapter
from agent_sync.skill_adapters.vscode import VSCodeSkillAdapter
from agent_sync.skill_adapters.windsurf import WindsurfSkillAdapter

__all__ = [
    "SkillAdapter",
    "CompatibilityReport",
    "CompatibilityStatus",
    "InstallResult",
    "CodexSkillAdapter",
    "ClaudeSkillAdapter",
    "CopilotSkillAdapter",
    "AntigravitySkillAdapter",
    "CursorSkillAdapter",
    "VSCodeSkillAdapter",
    "WindsurfSkillAdapter",
]
