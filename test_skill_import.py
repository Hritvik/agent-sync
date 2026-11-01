#!/usr/bin/env python3
"""Test script for skill import from Codex."""

from pathlib import Path

from agent_sync.paths import get_skills_dir, ensure_skills_dir
from agent_sync.skills import import_skills_from_codex

# Ensure canonical skills directory exists
ensure_skills_dir()
skills_dir = get_skills_dir()

print(f"Canonical skills directory: {skills_dir}")
print(f"Skills directory exists: {skills_dir.exists()}")
print()

# Test dry-run import from Codex
print("Testing dry-run import from Codex...")
results = import_skills_from_codex(skills_dir, dry_run=True, copy_mode=True)

print(f"\nFound {len(results)} skills:")
for skill_name, status, message in results:
    print(f"  {skill_name}: {status} - {message}")

print(f"\nSummary:")
print(f"  Total: {len(results)}")
print(f"  Dry-run: {sum(1 for _, s, _ in results if s == 'dry-run')}")
print(f"  Skipped: {sum(1 for _, s, _ in results if s == 'skipped')}")
print(f"  Conflict: {sum(1 for _, s, _ in results if s == 'conflict')}")
print(f"  Error: {sum(1 for _, s, _ in results if s == 'error')}")
