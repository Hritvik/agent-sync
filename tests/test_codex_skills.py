"""Filesystem integration coverage for Codex's shared skill store."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_sync.models import SkillDefinition, SkillSource
from agent_sync.skill_adapters.codex import CodexSkillAdapter


class CodexSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.project = self.home / "project"
        self.project.mkdir()
        self.patches = [
            patch("pathlib.Path.home", return_value=self.home),
            patch("pathlib.Path.cwd", return_value=self.project),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.adapter = CodexSkillAdapter()

    def skill(self, root=None):
        source = (root or self.home / ".agents/skills") / "example"
        source.mkdir(parents=True, exist_ok=True)
        (source / "SKILL.md").write_text("---\nname: example\ndescription: Example\n---\n")
        return SkillDefinition(
            name="example",
            description="Example",
            source=SkillSource(type="local", path=str(source)),
        )

    def test_discovery_locations_and_strategy(self):
        self.assertEqual(
            self.adapter.personal_skill_locations(),
            [self.home / ".agents/skills", self.home / ".codex/skills"],
        )
        self.assertEqual(
            self.adapter.project_skill_locations(self.project), [self.project / ".agents/skills"]
        )
        self.assertTrue(self.adapter.supports_symlinks())
        self.assertEqual(self.adapter.get_preferred_strategy(), "native")

    def test_native_validates_skill_exists_in_discovery_location(self):
        skill = self.skill()
        self.assertTrue(self.adapter.install(skill, "user", "native").success)
        Path(skill.source.path, "SKILL.md").unlink()
        self.assertFalse(self.adapter.install(skill, "user", "native").success)

    def test_native_rejects_external_source_and_accepts_project(self):
        self.assertFalse(
            self.adapter.install(self.skill(self.home / "authored"), "user", "native").success
        )
        self.assertTrue(
            self.adapter.install(
                self.skill(self.project / ".agents/skills"), "project", "native"
            ).success
        )

    def test_symlink_is_idempotent_and_supports_cli_personal_scope(self):
        skill = self.skill(self.home / "authored")
        for _ in range(2):
            self.assertTrue(self.adapter.install(skill, "personal", "symlink").success)
        self.assertTrue((self.home / ".agents/skills/example").is_symlink())

    def test_project_link_preserves_source(self):
        skill = self.skill()
        self.assertTrue(self.adapter.install(skill, "project", "symlink").success)
        self.assertTrue((self.project / ".agents/skills/example").is_symlink())
        self.assertTrue(Path(skill.source.path, "SKILL.md").exists())

    def test_collisions_including_broken_links_are_preserved(self):
        skill = self.skill(self.home / "authored")
        destination = self.home / ".agents/skills/example"
        destination.parent.mkdir(parents=True)
        destination.symlink_to(self.home / "missing")
        self.assertFalse(self.adapter.install(skill, "user", "symlink").success)
        self.assertTrue(destination.is_symlink())
        destination.unlink()
        destination.mkdir()
        self.assertFalse(self.adapter.install(skill, "user", "symlink").success)
        self.assertTrue(destination.is_dir())

    def test_native_removal_preserves_shared_and_legacy_content(self):
        for root in (self.home / ".agents/skills", self.home / ".codex/skills"):
            self.skill(root)
        self.assertFalse(self.adapter.uninstall("example", "user").success)
        self.assertTrue((self.home / ".agents/skills/example/SKILL.md").exists())
        self.assertTrue((self.home / ".codex/skills/example/SKILL.md").exists())

    def test_install_rejects_unvalidated_path_traversal(self):
        skill = self.skill().model_copy(update={"name": "../outside"})
        self.assertFalse(self.adapter.install(skill, "user", "symlink").success)

    def test_uninstall_rejects_path_traversal(self):
        self.assertFalse(self.adapter.uninstall("../outside", "user").success)

    def test_invalid_scope_strategy_and_missing_source(self):
        skill = self.skill()
        self.assertFalse(self.adapter.install(skill, "invalid", "native").success)
        self.assertFalse(self.adapter.install(skill, "user", "unknown").success)
        self.assertFalse(
            self.adapter.install(
                skill.model_copy(update={"source": SkillSource(type="git")}), "user", "symlink"
            ).success
        )
        self.assertFalse(self.adapter.uninstall("example", "invalid").success)

    def test_description_over_old_limit_is_compatible(self):
        skill = self.skill().model_copy(update={"description": "x" * 700})
        self.assertFalse(self.adapter.inspect_compatibility(skill).has_issues())

    def test_detect_compatibility_and_reload(self):
        self.assertFalse(self.adapter.detect())
        (self.home / ".codex").mkdir()
        (self.home / ".codex/config.toml").touch()
        self.assertTrue(self.adapter.detect())
        self.assertTrue(self.adapter.inspect_compatibility(self.skill()).is_compatible())
        self.assertIn("restart", self.adapter.reload_instructions().lower())


if __name__ == "__main__":
    unittest.main()
