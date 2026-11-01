"""Backup and atomic write utilities."""

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_sync.exceptions import BackupError
from agent_sync.paths import get_backups_dir


def create_backup(config_path: Path, client_name: str) -> Path:
    """Create a backup of a configuration file."""
    if not config_path.exists():
        raise BackupError(f"Cannot backup non-existent file: {config_path}")

    backups_dir = get_backups_dir() / client_name
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    backup_filename = f"{timestamp}-{config_path.name}"
    backup_path = backups_dir / backup_filename

    try:
        shutil.copy2(config_path, backup_path)
        return backup_path
    except OSError as e:
        raise BackupError(f"Failed to create backup: {e}") from e


def list_backups(client_name: str) -> list[Path]:
    """List all backups for a client."""
    backups_dir = get_backups_dir() / client_name
    if not backups_dir.exists():
        return []

    return sorted(backups_dir.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_backup(backup_path: Path, config_path: Path) -> None:
    """Restore a configuration file from backup."""
    if not backup_path.exists():
        raise BackupError(f"Backup file not found: {backup_path}")

    try:
        shutil.copy2(backup_path, config_path)
    except OSError as e:
        raise BackupError(f"Failed to restore backup: {e}") from e


def write_atomically(path: Path, content: str, validate: bool = True) -> None:
    """Write content to a file atomically.

    Args:
        path: The file path to write to
        content: The content to write
        validate: If True, parse the content after writing to ensure it's valid

    Raises:
        BackupError: If the write fails or validation fails
    """
    # Create parent directory if it doesn't exist
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write to a temporary file first
    temp_path = path.with_suffix(path.suffix + ".tmp")
    
    try:
        with open(temp_path, "w") as f:
            f.write(content)
        
        # If validation is requested and the file is JSON, try to parse it
        if validate and path.suffix in {".json", ".jsonc"}:
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                temp_path.unlink(missing_ok=True)
                raise BackupError(f"Generated JSON is invalid: {e}") from e
        
        # Atomic rename
        temp_path.replace(path)
    except OSError as e:
        temp_path.unlink(missing_ok=True)
        raise BackupError(f"Failed to write file atomically: {e}") from e


def compute_config_hash(config: dict[str, Any]) -> str:
    """Compute a hash of a configuration dict for change detection."""
    # Use deterministic JSON serialization
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode()).hexdigest()


def cleanup_old_backups(client_name: str, keep_count: int = 10) -> None:
    """Clean up old backups, keeping only the most recent ones."""
    backups = list_backups(client_name)
    
    if len(backups) <= keep_count:
        return
    
    # Remove oldest backups
    for backup in backups[keep_count:]:
        try:
            backup.unlink()
        except OSError:
            # Ignore errors during cleanup
            pass
