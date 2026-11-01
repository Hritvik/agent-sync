"""Skill validation and loading logic."""

import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from agent_sync.exceptions import ValidationError as McpSyncValidationError
from agent_sync.models import SkillDefinition, SkillSource, SkillRegistry
from agent_sync.paths import get_skills_dir, get_skills_registry_path


class SkillValidationError(Exception):
    """Error during skill validation."""

    def __init__(self, message: str, skill_path: str | None = None, field: str | None = None):
        self.message = message
        self.skill_path = skill_path
        self.field = field
        super().__init__(message)


def parse_skill_frontmatter(skill_path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a SKILL.md file."""
    if not skill_path.exists():
        raise SkillValidationError(f"SKILL.md not found", str(skill_path))

    content = skill_path.read_text(encoding="utf-8")

    # Check for YAML frontmatter
    if not content.startswith("---"):
        raise SkillValidationError(f"SKILL.md must start with YAML frontmatter (---)", str(skill_path))

    # Extract frontmatter
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise SkillValidationError(f"SKILL.md must have closing --- for frontmatter", str(skill_path))

    frontmatter_text = parts[1].strip()
    body = parts[2].strip()

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            raise SkillValidationError(f"Frontmatter must be a YAML object", str(skill_path))
        return frontmatter
    except yaml.YAMLError as e:
        raise SkillValidationError(f"Invalid YAML in frontmatter: {e}", str(skill_path))


def validate_skill_frontmatter(frontmatter: dict[str, Any], skill_path: Path) -> None:
    """Validate SKILL.md frontmatter against Agent Skills specification."""
    # Required fields
    if "name" not in frontmatter:
        raise SkillValidationError(f"Missing required field: name", str(skill_path), "name")
    
    if "description" not in frontmatter:
        raise SkillValidationError(f"Missing required field: description", str(skill_path), "description")

    name = frontmatter["name"]
    description = frontmatter["description"]

    # Validate name
    if not isinstance(name, str):
        raise SkillValidationError(f"Field 'name' must be a string", str(skill_path), "name")
    
    if not name:
        raise SkillValidationError(f"Field 'name' cannot be empty", str(skill_path), "name")
    
    if len(name) > 64:
        raise SkillValidationError(f"Field 'name' must be 64 characters or less (got {len(name)})", str(skill_path), "name")
    
    if not re.match(r"^[a-z0-9-]+$", name):
        raise SkillValidationError(
            f"Field 'name' must contain only lowercase letters, numbers, and hyphens", str(skill_path), "name"
        )
    
    if name.startswith("-") or name.endswith("-"):
        raise SkillValidationError(f"Field 'name' cannot start or end with a hyphen", str(skill_path), "name")
    
    if "--" in name:
        raise SkillValidationError(f"Field 'name' cannot contain consecutive hyphens", str(skill_path), "name")

    # Validate description
    if not isinstance(description, str):
        raise SkillValidationError(f"Field 'description' must be a string", str(skill_path), "description")
    
    if not description:
        raise SkillValidationError(f"Field 'description' cannot be empty", str(skill_path), "description")
    
    if len(description) > 1024:
        raise SkillValidationError(
            f"Field 'description' must be 1024 characters or less (got {len(description)})", 
            str(skill_path), 
            "description"
        )

    # Validate optional fields if present
    if "license" in frontmatter and not isinstance(frontmatter["license"], str):
        raise SkillValidationError(f"Field 'license' must be a string", str(skill_path), "license")
    
    if "compatibility" in frontmatter:
        compat = frontmatter["compatibility"]
        if not isinstance(compat, str):
            raise SkillValidationError(f"Field 'compatibility' must be a string", str(skill_path), "compatibility")
        if len(compat) > 500:
            raise SkillValidationError(
                f"Field 'compatibility' must be 500 characters or less (got {len(compat)})",
                str(skill_path),
                "compatibility"
            )
    
    if "metadata" in frontmatter and not isinstance(frontmatter["metadata"], dict):
        raise SkillValidationError(f"Field 'metadata' must be an object", str(skill_path), "metadata")


def validate_skill_directory(skill_dir: Path) -> None:
    """Validate that a skill directory structure is correct."""
    if not skill_dir.exists():
        raise SkillValidationError(f"Skill directory does not exist: {skill_dir}")
    
    if not skill_dir.is_dir():
        raise SkillValidationError(f"Skill path is not a directory: {skill_dir}")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        raise SkillValidationError(f"SKILL.md not found in skill directory: {skill_dir}")

    # Check directory name matches skill name
    frontmatter = parse_skill_frontmatter(skill_md)
    skill_name = frontmatter.get("name")
    if skill_name and skill_dir.name != skill_name:
        raise SkillValidationError(
            f"Directory name '{skill_dir.name}' does not match skill name '{skill_name}'",
            str(skill_dir)
        )

    # Check for suspicious files
    for item in skill_dir.iterdir():
        if item.is_file() and item.name not in ["SKILL.md", "LICENSE", "LICENSE.txt"]:
            # Warn about executable files
            if item.suffix in [".sh", ".bash", ".py", ".js", ".exe", ".bat"]:
                # This is a warning, not an error
                pass


def compute_skill_hash(skill_dir: Path) -> str:
    """Compute SHA256 hash of skill directory contents."""
    hasher = hashlib.sha256()
    
    # Hash SKILL.md
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        hasher.update(skill_md.read_bytes())
    
    # Hash other files in deterministic order
    for file_path in sorted(skill_dir.rglob("*")):
        if file_path.is_file() and file_path.name != "SKILL.md":
            hasher.update(file_path.read_bytes())
    
    return f"sha256:{hasher.hexdigest()}"


def load_skill_from_directory(skill_dir: Path, source: SkillSource) -> SkillDefinition:
    """Load and validate a skill from a directory."""
    validate_skill_directory(skill_dir)
    
    skill_md = skill_dir / "SKILL.md"
    frontmatter = parse_skill_frontmatter(skill_md)
    validate_skill_frontmatter(frontmatter, skill_md)
    
    # Create skill definition
    skill_def = SkillDefinition(
        name=frontmatter["name"],
        description=frontmatter["description"],
        source=source,
        enabled=True,
        trust_state="unreviewed",
        content_hash=compute_skill_hash(skill_dir),
    )
    
    return skill_def


def discover_skills(skills_dir: Path) -> list[Path]:
    """Discover all skill directories in the canonical skills store."""
    if not skills_dir.exists():
        return []
    
    skill_dirs = []
    for item in skills_dir.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            skill_dirs.append(item)
    
    return sorted(skill_dirs)


def validate_all_skills(skills_dir: Path) -> list[tuple[Path, SkillValidationError | None]]:
    """Validate all skills in the canonical skills store."""
    skill_dirs = discover_skills(skills_dir)
    results = []
    
    for skill_dir in skill_dirs:
        try:
            validate_skill_directory(skill_dir)
            skill_md = skill_dir / "SKILL.md"
            frontmatter = parse_skill_frontmatter(skill_md)
            validate_skill_frontmatter(frontmatter, skill_md)
            results.append((skill_dir, None))
        except SkillValidationError as e:
            results.append((skill_dir, e))
    
    return results


def load_skill_registry() -> SkillRegistry:
    """Load the skill registry from disk."""
    registry_path = get_skills_registry_path()
    
    if not registry_path.exists():
        return SkillRegistry()
    
    content = registry_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    
    if not data:
        return SkillRegistry()
    
    return SkillRegistry.model_validate(data)


def save_skill_registry(registry: SkillRegistry) -> None:
    """Save the skill registry to disk."""
    registry_path = get_skills_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = yaml.dump(registry.model_dump(mode="json"), default_flow_style=False, sort_keys=False)
    registry_path.write_text(content, encoding="utf-8")


def import_skills_from_codex(
    skills_dir: Path,
    dry_run: bool = False,
    copy_mode: bool = False,
) -> list[tuple[str, str, str]]:
    """Import skills from Codex to the canonical store.
    
    Returns list of (skill_name, status, message) tuples.
    """
    codex_skills_dir = Path.home() / ".codex" / "skills"
    
    if not codex_skills_dir.exists():
        return [("codex", "error", f"Codex skills directory not found: {codex_skills_dir}")]
    
    # Discover Codex skills
    codex_skill_dirs = []
    for item in codex_skills_dir.iterdir():
        if item.is_dir() and (item / "SKILL.md").exists():
            # Skip .system skills
            if item.name.startswith("."):
                continue
            codex_skill_dirs.append(item)
    
    results = []
    existing_registry = load_skill_registry()
    
    for skill_dir in sorted(codex_skill_dirs):
        skill_name = skill_dir.name
        dest_dir = skills_dir / skill_name
        
        # Check if skill already exists in canonical store
        if skill_name in existing_registry.skills:
            # Compare hashes to detect changes
            existing_skill = existing_registry.skills[skill_name]
            current_hash = compute_skill_hash(skill_dir)
            
            if existing_skill.content_hash == current_hash:
                results.append((skill_name, "skipped", "Already exists with same content"))
                continue
            else:
                results.append((skill_name, "conflict", f"Already exists with different content (existing: {existing_skill.content_hash[:16]}..., current: {current_hash[:16]}...)"))
                continue
        
        if dry_run:
            results.append((skill_name, "dry-run", f"Would import from {skill_dir} to {dest_dir}"))
            continue
        
        # Validate skill before importing
        try:
            validate_skill_directory(skill_dir)
            skill_md = skill_dir / "SKILL.md"
            frontmatter = parse_skill_frontmatter(skill_md)
            validate_skill_frontmatter(frontmatter, skill_md)
        except SkillValidationError as e:
            results.append((skill_name, "error", f"Validation failed: {e.message}"))
            continue
        
        # Import skill
        if copy_mode:
            # Copy the skill directory
            if dest_dir.exists():
                results.append((skill_name, "error", f"Destination already exists: {dest_dir}"))
                continue
            
            shutil.copytree(skill_dir, dest_dir)
            results.append((skill_name, "copied", f"Copied from {skill_dir} to {dest_dir}"))
        else:
            # Move the skill directory
            if dest_dir.exists():
                results.append((skill_name, "error", f"Destination already exists: {dest_dir}"))
                continue
            
            shutil.move(str(skill_dir), str(dest_dir))
            results.append((skill_name, "moved", f"Moved from {skill_dir} to {dest_dir}"))
        
        # Add to registry
        source = SkillSource(
            type="client",
            client="codex",
            path=str(skill_dir),
        )
        
        skill_def = load_skill_from_directory(dest_dir, source)
        existing_registry.skills[skill_name] = skill_def
    
    # Save updated registry
    if not dry_run:
        save_skill_registry(existing_registry)
    
    return results
